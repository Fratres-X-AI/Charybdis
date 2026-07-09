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
    depth_rate_tau_s: float = 10.0
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
    POS = slice(0, 2)
    DEPTH = 2
    VEL = slice(3, 5)
    DEPTH_RATE = 5
    BIAS = slice(6, 8)

    def __init__(self, pos0, vel0=(0.0, 0.0), depth0: float = 0.0,
                 cfg: HybridFusionConfig | None = None,
                 initial_mode: NavMode = NavMode.SURFACE):
        if isinstance(depth0, HybridFusionConfig) and cfg is None:
            cfg = depth0
            depth0 = 0.0
        self.cfg = cfg or HybridFusionConfig()
        self.mode_mgr = ModeManager(self.cfg.mode, initial=initial_mode)
        self.x = np.zeros(self.N, dtype=float)
        self.x[self.POS] = np.asarray(pos0, dtype=float)
        self.x[self.DEPTH] = float(depth0)
        self.x[self.VEL] = np.asarray(vel0, dtype=float)
        p = np.zeros(self.N)
        p[self.POS] = self.cfg.init_pos_std ** 2
        p[self.DEPTH] = self.cfg.init_depth_std ** 2
        p[self.VEL] = self.cfg.init_vel_std ** 2
        p[self.DEPTH_RATE] = self.cfg.init_depth_rate_std ** 2
        p[self.BIAS] = self.cfg.init_bias_std ** 2
        self.P = np.diag(p)
        self.t = 0.0
        self.last_gps_t: float | None = None
        self.last_bathy_t: float | None = None
        self.rejections: list[tuple[float, str, float]] = []

    def step(self, packet: SensorPacket) -> HybridNavState:
        if packet.imu is not None and packet.imu.quality.available:
            self.predict(packet.imu)

        depth_for_mode = self.x[self.DEPTH]
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
        if not np.isfinite(dt) or dt <= 0.0:
            raise ValueError("IMU dt must be positive and finite")
        self.t += dt
        accel = np.asarray(imu.accel, dtype=float)
        if accel.shape != (2,) or not np.all(np.isfinite(accel)):
            raise ValueError("IMU accel must be a finite 2-vector")
        a = accel - self.x[self.BIAS]
        self.x[self.POS] += self.x[self.VEL] * dt + 0.5 * a * dt * dt
        self.x[self.DEPTH] += self.x[self.DEPTH_RATE] * dt
        tau = max(self.cfg.depth_rate_tau_s, 1e-6)
        self.x[self.DEPTH_RATE] *= np.exp(-dt / tau)
        self.x[self.VEL] += a * dt

        F = np.eye(self.N)
        F[self.POS, self.VEL] = np.eye(2) * dt
        F[self.POS, self.BIAS] = -0.5 * dt * dt * np.eye(2)
        F[self.DEPTH, self.DEPTH_RATE] = dt
        F[self.VEL, self.BIAS] = -dt * np.eye(2)

        q_a = (self.cfg.accel_noise * max(imu.quality.scale, 1e-6)) ** 2
        q_z_acc = self.cfg.depth_rate_noise ** 2
        q_z_rw = self.cfg.depth_process_noise ** 2
        q_b = self.cfg.accel_bias_rw ** 2
        dt2 = dt * dt
        dt3 = dt2 * dt
        Q = np.zeros((self.N, self.N))
        Q[0:2, 0:2] = np.eye(2) * (q_a * dt3 / 3.0)
        Q[0:2, 3:5] = np.eye(2) * (q_a * dt2 / 2.0)
        Q[3:5, 0:2] = np.eye(2) * (q_a * dt2 / 2.0)
        Q[3:5, 3:5] = np.eye(2) * (q_a * dt)
        Q[6:8, 6:8] = np.eye(2) * (q_b * dt)
        Q[self.DEPTH, self.DEPTH] = q_z_acc * dt3 / 3.0 + q_z_rw * dt
        Q[self.DEPTH, self.DEPTH_RATE] = q_z_acc * dt2 / 2.0
        Q[self.DEPTH_RATE, self.DEPTH] = q_z_acc * dt2 / 2.0
        Q[self.DEPTH_RATE, self.DEPTH_RATE] = q_z_acc * dt
        self.P = self._stabilize_cov(F @ self.P @ F.T + Q)

    def update_depth(self, meas: DepthMeasurement) -> bool:
        if not meas.quality.available or not np.isfinite(meas.depth_m):
            return False
        return self._update_linear(
            np.array([float(meas.depth_m)]),
            meas.quality.apply(np.array([[float(meas.var)]])),
            [self.DEPTH],
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
        nis = float(y @ np.linalg.solve(S, y))
        if nis > gate:
            self.rejections.append((self.t, source, nis))
            return False
        K = np.linalg.solve(S, H @ self.P).T
        self.x = self.x + K @ y
        I = np.eye(self.N)
        A = I - K @ H
        self.P = self._stabilize_cov(A @ self.P @ A.T + K @ R @ K.T)
        return True

    def state(self) -> HybridNavState:
        return HybridNavState(
            pos=self.x[self.POS].copy(),
            vel=self.x[self.VEL].copy(),
            cov=self.P.copy(),
            mode=self.mode_mgr.mode,
            t=self.t,
            depth_m=float(self.x[self.DEPTH]),
            depth_rate_mps=float(self.x[self.DEPTH_RATE]),
            last_gps_t=self.last_gps_t,
            last_bathy_t=self.last_bathy_t,
        )

    def reset(self, pos, vel=None, pos_cov=None,
              depth_m: float | None = None) -> HybridNavState:
        self.x[self.POS] = np.asarray(pos, dtype=float)
        self._reset_block([0, 1], pos_cov if pos_cov is not None
                          else np.diag([self.cfg.init_pos_std] * 2) ** 2)
        if vel is not None:
            self.x[self.VEL] = np.asarray(vel, dtype=float)
            self._reset_block([3, 4], np.diag([self.cfg.init_vel_std] * 2) ** 2)
        else:
            self._reset_block([3, 4], np.diag([self.cfg.init_vel_std] * 2) ** 2)
        if depth_m is not None:
            self.x[self.DEPTH] = float(depth_m)
            self.x[self.DEPTH_RATE] = 0.0
            self._reset_block(
                [self.DEPTH, self.DEPTH_RATE],
                np.diag([self.cfg.init_depth_std, self.cfg.init_depth_rate_std]) ** 2,
            )
        self.P = self._stabilize_cov(self.P)
        return self.state()

    def _reset_block(self, idx: list[int], cov: np.ndarray) -> None:
        self.P[idx, :] = 0.0
        self.P[:, idx] = 0.0
        self.P[np.ix_(idx, idx)] = self._stabilize_cov(cov)

    def _stabilize_cov(self, M: np.ndarray) -> np.ndarray:
        M = self._sym(np.asarray(M, dtype=float))
        w, V = np.linalg.eigh(M)
        w = np.maximum(w, self.cfg.min_cov)
        return self._sym((V * w) @ V.T)

    @staticmethod
    def _sym(M: np.ndarray) -> np.ndarray:
        return 0.5 * (M + M.T)
