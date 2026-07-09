# Grokky Code Review Packet

## `charybdis/fusion.py`

```python
"""Hybrid surface/submerged sensor fusion for harbor-patrol UUVs."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .modes import ModeManager, ModeManagerConfig, NavMode
from .sensors import (BathymetryMeasurement, DepthMeasurement, GpsMeasurement,
                      ImuMeasurement, SensorPacket, VelocityMeasurement)


@dataclass(frozen=True)
class HybridFusionConfig:
    init_pos_std: float = 25.0
    init_depth_std: float = 1.0
    init_vel_std: float = 0.5
    init_depth_rate_std: float = 0.15
    init_bias_std: float = 0.05
    accel_noise: float = 0.08
    depth_process_noise: float = 0.05
    depth_rate_noise: float = 0.03
    accel_bias_rw: float = 0.002
    gps_gate_chi2: float = 25.0
    depth_gate_chi2: float = 9.0
    velocity_gate_chi2: float = 16.0
    bathy_gate_chi2: float = 25.0
    min_cov: float = 1e-6
    mode: ModeManagerConfig = ModeManagerConfig()


@dataclass(frozen=True)
class HybridNavState:
    pos: np.ndarray
    vel: np.ndarray
    cov: np.ndarray
    mode: NavMode
    t: float
    depth_m: float = 0.0
    depth_rate_mps: float = 0.0
    last_gps_t: float | None = None
    last_bathy_t: float | None = None

    @property
    def pos_cov(self) -> np.ndarray:
        return self.cov[0:2, 0:2]

    @property
    def pos_std(self) -> np.ndarray:
        return np.sqrt(np.clip(np.diag(self.pos_cov), 0.0, None))

    @property
    def depth_std(self) -> float:
        return float(np.sqrt(max(self.cov[2, 2], 0.0)))


class HybridSensorFusion:
    """Modular fusion core for abstract UUV sensor inputs."""

    N = 8  # px, py, depth, vx, vy, depth_rate, bax, bay

    def __init__(self, pos0, vel0=(0.0, 0.0), depth0: float = 0.0,
                 cfg: HybridFusionConfig | None = None,
                 initial_mode: NavMode = NavMode.SURFACE):
        if isinstance(depth0, HybridFusionConfig) and cfg is None:
            cfg = depth0
            depth0 = 0.0
        self.cfg = cfg or HybridFusionConfig()
        self.mode_mgr = ModeManager(self.cfg.mode, initial=initial_mode)
        self.x = np.zeros(self.N, dtype=float)
        self.x[0:2] = np.asarray(pos0, dtype=float)
        self.x[2] = float(depth0)
        self.x[3:5] = np.asarray(vel0, dtype=float)
        p = np.zeros(self.N)
        p[0:2] = self.cfg.init_pos_std ** 2
        p[2] = self.cfg.init_depth_std ** 2
        p[3:5] = self.cfg.init_vel_std ** 2
        p[5] = self.cfg.init_depth_rate_std ** 2
        p[6:8] = self.cfg.init_bias_std ** 2
        self.P = np.diag(p)
        self.t = 0.0
        self.last_gps_t: float | None = None
        self.last_bathy_t: float | None = None
        self.rejections: list[tuple[float, str, float]] = []

    def step(self, packet: SensorPacket) -> HybridNavState:
        if packet.imu is not None and packet.imu.quality.available:
            self.predict(packet.imu)

        depth_for_mode = self.x[2]
        if packet.depth is not None and packet.depth.quality.available \
                and np.isfinite(packet.depth.depth_m):
            depth_for_mode = float(packet.depth.depth_m)
        mode = self.mode_mgr.update(depth_m=depth_for_mode, hint=packet.mode_hint)

        if packet.velocity is not None:
            self.update_velocity(packet.velocity)
        if packet.depth is not None:
            self.update_depth(packet.depth)
        if packet.bathymetry is not None and mode == NavMode.SUBMERGED:
            if self.update_bathymetry(packet.bathymetry):
                self.last_bathy_t = self.t
        if packet.gps is not None and mode == NavMode.SURFACE:
            if self.update_gps(packet.gps):
                self.last_gps_t = self.t

        return self.state()

    def predict(self, imu: ImuMeasurement) -> None:
        dt = float(imu.dt)
        self.t += dt
        a = np.asarray(imu.accel, dtype=float) - self.x[6:8]
        self.x[0:2] += self.x[3:5] * dt + 0.5 * a * dt * dt
        self.x[2] += self.x[5] * dt
        self.x[3:5] += a * dt

        F = np.eye(self.N)
        F[0:2, 3:5] = np.eye(2) * dt
        F[0:2, 6:8] = -0.5 * dt * dt * np.eye(2)
        F[2, 5] = dt
        F[3:5, 6:8] = -dt * np.eye(2)

        q_a = (self.cfg.accel_noise * max(imu.quality.scale, 1e-6)) ** 2
        q_z = self.cfg.depth_process_noise ** 2
        q_b = self.cfg.accel_bias_rw ** 2
        Q = np.zeros((self.N, self.N))
        for i in range(2):
            Q[i, i] = q_a * dt ** 3 / 3.0
            Q[i, i + 3] = Q[i + 3, i] = q_a * dt ** 2 / 2.0
            Q[i + 3, i + 3] = q_a * dt
            Q[i + 6, i + 6] = q_b * dt
        Q[2, 2] = q_z * dt ** 3 / 3.0
        Q[2, 5] = Q[5, 2] = q_z * dt ** 2 / 2.0
        Q[5, 5] = q_z * dt + self.cfg.depth_rate_noise ** 2 * dt
        self.P = self._stabilize_cov(F @ self.P @ F.T + Q)

    def update_depth(self, meas: DepthMeasurement) -> bool:
        if not meas.quality.available or not np.isfinite(meas.depth_m):
            return False
        return self._update_linear(
            np.array([float(meas.depth_m)]),
            meas.quality.apply(np.array([[float(meas.var)]])),
            [2],
            self.cfg.depth_gate_chi2,
            "depth",
        )

    def update_gps(self, gps: GpsMeasurement) -> bool:
        if not gps.quality.available:
            return False
        ok_pos = self._update_linear(gps.pos, gps.quality.apply(gps.pos_cov),
                                     [0, 1], self.cfg.gps_gate_chi2, "gps_pos")
        ok_vel = True
        if gps.vel is not None:
            cov = gps.vel_cov if gps.vel_cov is not None else np.diag([0.15, 0.15]) ** 2
            ok_vel = self._update_linear(gps.vel, gps.quality.apply(cov),
                                         [3, 4], self.cfg.velocity_gate_chi2,
                                         "gps_vel")
        return ok_pos or ok_vel

    def update_velocity(self, vel: VelocityMeasurement) -> bool:
        if not vel.quality.available:
            return False
        return self._update_linear(vel.vel, vel.quality.apply(vel.cov), [3, 4],
                                   self.cfg.velocity_gate_chi2, "velocity")

    def update_bathymetry(self, meas: BathymetryMeasurement) -> bool:
        if not meas.quality.available:
            return False
        pos, cov = meas.as_position_fix()
        return self._update_linear(pos, cov, [0, 1], self.cfg.bathy_gate_chi2,
                                   "bathymetry")

    def _update_linear(self, z: np.ndarray, R: np.ndarray, idx: list[int],
                       gate: float, source: str) -> bool:
        z = np.asarray(z, dtype=float)
        R = np.asarray(R, dtype=float)
        if not np.all(np.isfinite(z)) or not np.all(np.isfinite(R)):
            return False
        R = self._stabilize_cov(R)
        H = np.zeros((len(idx), self.N))
        for row, col in enumerate(idx):
            H[row, col] = 1.0
        y = z - H @ self.x
        S = self._stabilize_cov(H @ self.P @ H.T + R)
        nis = float(y @ np.linalg.inv(S) @ y)
        if nis > gate:
            self.rejections.append((self.t, source, nis))
            return False
        K = self.P @ H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        I = np.eye(self.N)
        A = I - K @ H
        self.P = self._stabilize_cov(A @ self.P @ A.T + K @ R @ K.T)
        return True

    def state(self) -> HybridNavState:
        return HybridNavState(
            pos=self.x[0:2].copy(),
            vel=self.x[3:5].copy(),
            cov=self.P.copy(),
            mode=self.mode_mgr.mode,
            t=self.t,
            depth_m=float(self.x[2]),
            depth_rate_mps=float(self.x[5]),
            last_gps_t=self.last_gps_t,
            last_bathy_t=self.last_bathy_t,
        )

    def reset(self, pos, vel=None, pos_cov=None,
              depth_m: float | None = None) -> HybridNavState:
        self.x[0:2] = np.asarray(pos, dtype=float)
        if vel is not None:
            self.x[3:5] = np.asarray(vel, dtype=float)
        if depth_m is not None:
            self.x[2] = float(depth_m)
        self.P[0:2, :] = 0.0
        self.P[:, 0:2] = 0.0
        self.P[0:2, 0:2] = self._stabilize_cov(
            pos_cov if pos_cov is not None else np.diag([self.cfg.init_pos_std] * 2) ** 2)
        if depth_m is not None:
            self.P[2, :] = 0.0
            self.P[:, 2] = 0.0
            self.P[2, 2] = self.cfg.init_depth_std ** 2
        self.P = self._stabilize_cov(self.P)
        return self.state()

    def _stabilize_cov(self, M: np.ndarray) -> np.ndarray:
        M = self._sym(np.asarray(M, dtype=float))
        w, V = np.linalg.eigh(M)
        w = np.maximum(w, self.cfg.min_cov)
        return self._sym((V * w) @ V.T)

    @staticmethod
    def _sym(M: np.ndarray) -> np.ndarray:
        return 0.5 * (M + M.T)
```

## `charybdis/patrol.py`

```python
"""Repeatable waypoint patrol execution for hybrid surface/submerged routes."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .fusion import HybridNavState
from .modes import NavMode


@dataclass(frozen=True)
class Waypoint:
    pos: np.ndarray
    mode: NavMode = NavMode.SURFACE
    depth_m: float = 0.0
    speed_mps: float = 1.5
    radius_m: float = 5.0
    heading_rad: float | None = None
    heading_tolerance_rad: float = np.deg2rad(20.0)
    lookahead_m: float = 12.0

    def __post_init__(self):
        p = np.asarray(self.pos, dtype=float)
        if p.shape != (2,):
            raise ValueError("waypoint pos must be a 2-vector")
        object.__setattr__(self, "pos", p)


@dataclass(frozen=True)
class PatrolRoute:
    waypoints: tuple[Waypoint, ...]
    loop: bool = False

    def __post_init__(self):
        if not self.waypoints:
            raise ValueError("patrol route needs at least one waypoint")


@dataclass(frozen=True)
class PatrolCommand:
    target_pos: np.ndarray
    desired_vel: np.ndarray
    desired_heading_rad: float
    target_depth_m: float
    target_mode: NavMode
    waypoint_index: int
    route_complete: bool = False


class PatrolExecutor:
    """Small route follower with explicit resume support."""

    def __init__(self, route: PatrolRoute):
        self.route = route
        self.index = 0
        self.complete = False

    def update(self, state: HybridNavState) -> PatrolCommand:
        wp = self.route.waypoints[self.index]
        delta = wp.pos - state.pos
        dist = float(np.linalg.norm(delta))
        desired_heading = self._bearing(delta, state.vel)
        if dist <= wp.radius_m and self._heading_ok(state, wp, desired_heading):
            self._advance()
            wp = self.route.waypoints[self.index]
            delta = self._carrot_target(state.pos, wp) - state.pos
            dist = float(np.linalg.norm(delta))
            desired_heading = self._bearing(delta, state.vel)
        else:
            delta = self._carrot_target(state.pos, wp) - state.pos
            dist = float(np.linalg.norm(delta))
            desired_heading = self._bearing(delta, state.vel)

        if dist > 1e-9 and not self.complete:
            desired = delta / dist * wp.speed_mps
        else:
            desired = np.zeros(2)

        return PatrolCommand(
            target_pos=wp.pos.copy(),
            desired_vel=desired,
            desired_heading_rad=float(desired_heading),
            target_depth_m=float(wp.depth_m),
            target_mode=wp.mode,
            waypoint_index=self.index,
            route_complete=self.complete,
        )

    def resume(self, pos: np.ndarray) -> int:
        """Resume at the nearest waypoint after surfacing/diving or restart."""
        p = np.asarray(pos, dtype=float)
        d = [float(np.linalg.norm(wp.pos - p)) for wp in self.route.waypoints]
        self.index = int(np.argmin(d))
        self.complete = False
        return self.index

    def set_index(self, index: int) -> None:
        if not 0 <= index < len(self.route.waypoints):
            raise IndexError(index)
        self.index = int(index)
        self.complete = False

    def _advance(self) -> None:
        if self.complete:
            return
        nxt = self.index + 1
        if nxt < len(self.route.waypoints):
            self.index = nxt
        elif self.route.loop:
            self.index = 0
        else:
            self.complete = True

    def _carrot_target(self, pos: np.ndarray, wp: Waypoint) -> np.ndarray:
        if self.index == 0:
            return wp.pos
        prev = self.route.waypoints[self.index - 1].pos
        seg = wp.pos - prev
        seg_len = float(np.linalg.norm(seg))
        if seg_len < 1e-9:
            return wp.pos
        u = seg / seg_len
        along = float(np.clip((pos - prev) @ u, 0.0, seg_len))
        carrot = prev + u * min(seg_len, along + max(wp.lookahead_m, wp.radius_m))
        return carrot

    @staticmethod
    def _bearing(delta: np.ndarray, fallback_vel: np.ndarray) -> float:
        if np.linalg.norm(delta) > 1e-9:
            return float(np.arctan2(delta[1], delta[0]))
        if np.linalg.norm(fallback_vel) > 1e-9:
            return float(np.arctan2(fallback_vel[1], fallback_vel[0]))
        return 0.0

    @staticmethod
    def _heading_ok(state: HybridNavState, wp: Waypoint,
                    desired_heading: float) -> bool:
        target = desired_heading if wp.heading_rad is None else float(wp.heading_rad)
        if np.linalg.norm(state.vel) <= 1e-9:
            return wp.heading_rad is None
        current = float(np.arctan2(state.vel[1], state.vel[0]))
        return abs(_wrap_pi(current - target)) <= wp.heading_tolerance_rad


def _wrap_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)
```
