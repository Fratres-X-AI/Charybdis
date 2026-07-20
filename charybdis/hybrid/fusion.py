"""Hybrid surface/submerged sensor fusion for harbor-patrol UUVs."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
from typing import NamedTuple

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .bathymetry import MatchHealth
from .frames import compensate_measurement_latency
from .modes import ModeManager, ModeManagerConfig, NavMode
from .sensors import (
    BathymetryMeasurement,
    DepthMeasurement,
    GpsMeasurement,
    ImuMeasurement,
    SensorPacket,
    VelocityMeasurement,
)

FloatArray = NDArray[np.float64]


class NavDegradationLevel(StrEnum):
    """Explicit navigation health tier for downstream autonomy."""

    NOMINAL = "nominal"
    DEGRADED = "degraded"
    FAULT = "fault"


@dataclass(frozen=True)
class HybridFusionConfig:
    """Noise, gating, and initialization settings for hybrid fusion."""

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
    rejection_history_size: int = 256
    health_window_s: float = 30.0
    max_recent_rejections: int = 12
    max_position_std_m: float = 500.0
    aiding_timeout_s: float = 30.0
    mode: ModeManagerConfig = ModeManagerConfig()

    def __post_init__(self) -> None:
        positive = (
            "init_pos_std",
            "init_depth_std",
            "init_vel_std",
            "init_depth_rate_std",
            "init_bias_std",
            "depth_rate_tau_s",
            "gps_gate_chi2",
            "depth_gate_chi2",
            "velocity_gate_chi2",
            "bathy_gate_chi2",
            "min_cov",
            "health_window_s",
            "max_position_std_m",
            "aiding_timeout_s",
        )
        non_negative = (
            "accel_noise",
            "depth_process_noise",
            "depth_rate_noise",
            "accel_bias_rw",
        )
        for name in positive:
            value = float(getattr(self, name))
            if not np.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        for name in non_negative:
            value = float(getattr(self, name))
            if not np.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.rejection_history_size <= 0:
            raise ValueError("rejection_history_size must be positive")
        if self.max_recent_rejections < 0:
            raise ValueError("max_recent_rejections must be non-negative")


class FusionRejection(NamedTuple):
    """One rejected innovation."""

    t: float
    source: str
    nis: float
    gate: float


@dataclass(frozen=True)
class FusionDiagnostics:
    """Bounded health and aiding summary for autonomy consumers."""

    filter_healthy: bool = True
    total_rejections: int = 0
    recent_rejections: tuple[FusionRejection, ...] = ()
    aiding_sources: frozenset[str] = frozenset()
    degradation_level: NavDegradationLevel = NavDegradationLevel.NOMINAL
    bathy_confidence: float = 1.0
    bathy_trusted: bool = True


@dataclass(frozen=True)
class HybridNavState:
    """Immutable navigation estimate returned after each fusion step."""

    pos: FloatArray
    vel: FloatArray
    cov: FloatArray
    mode: NavMode
    t: float
    depth_m: float = 0.0
    depth_rate_mps: float = 0.0
    last_gps_t: float | None = None
    last_bathy_t: float | None = None
    diagnostics: FusionDiagnostics = field(default_factory=FusionDiagnostics)

    def __post_init__(self) -> None:
        pos = np.array(self.pos, dtype=np.float64, copy=True)
        vel = np.array(self.vel, dtype=np.float64, copy=True)
        cov = np.array(self.cov, dtype=np.float64, copy=True)
        if pos.shape != (2,) or vel.shape != (2,) or cov.shape != (8, 8):
            raise ValueError("state requires pos (2,), vel (2,), and cov (8, 8)")
        if not all(np.all(np.isfinite(value)) for value in (pos, vel, cov)):
            raise ValueError("state arrays must be finite")
        if not np.allclose(cov, cov.T, atol=1e-10):
            raise ValueError("state covariance must be symmetric")
        if np.linalg.eigvalsh(cov).min() < -1e-9:
            raise ValueError("state covariance must be positive semidefinite")
        if not np.isfinite(self.t) or self.t < 0.0:
            raise ValueError("state time must be finite and non-negative")
        if not np.isfinite(self.depth_m) or self.depth_m < 0.0:
            raise ValueError("depth_m must be finite and non-negative")
        if not np.isfinite(self.depth_rate_mps):
            raise ValueError("depth_rate_mps must be finite")
        pos.setflags(write=False)
        vel.setflags(write=False)
        cov.setflags(write=False)
        object.__setattr__(self, "pos", pos)
        object.__setattr__(self, "vel", vel)
        object.__setattr__(self, "cov", cov)
        object.__setattr__(self, "mode", NavMode(self.mode))

    @property
    def pos_cov(self) -> FloatArray:
        """Return the 2×2 horizontal position covariance."""
        return self.cov[0:2, 0:2]

    @property
    def pos_std(self) -> FloatArray:
        """Return horizontal one-sigma position uncertainty."""
        return np.sqrt(np.clip(np.diag(self.pos_cov), 0.0, None))

    @property
    def depth_std(self) -> float:
        """Return one-sigma depth uncertainty in metres."""
        return float(np.sqrt(max(self.cov[2, 2], 0.0)))

    @property
    def vel_cov(self) -> FloatArray:
        """Return the 2×2 horizontal velocity covariance."""
        return self.cov[3:5, 3:5]

    @property
    def error_radius_1sigma(self) -> float:
        """Return the conservative horizontal one-sigma error radius."""
        return float(np.sqrt(max(np.linalg.eigvalsh(self.pos_cov).max(), 0.0)))

    @property
    def filter_healthy(self) -> bool:
        """Return the estimator health decision."""
        return self.diagnostics.filter_healthy

    @property
    def aiding_sources(self) -> frozenset[str]:
        """Return recently accepted aiding source names."""
        return self.diagnostics.aiding_sources

    @property
    def degradation_level(self) -> NavDegradationLevel:
        """Return the current navigation degradation tier."""
        return self.diagnostics.degradation_level


class HybridSensorFusion:
    """Conservative 8D fusion for surface/submerged UUV navigation.

    The state is ``[px, py, depth, vx, vy, depth_rate, bax, bay]``. IMU
    measurements drive prediction, while GPS, depth, velocity, and bathymetry
    updates are quality-scaled and chi-square gated.
    """

    N = 8  # px, py, depth, vx, vy, depth_rate, bax, bay
    POS = slice(0, 2)
    DEPTH = 2
    VEL = slice(3, 5)
    DEPTH_RATE = 5
    BIAS = slice(6, 8)

    def __init__(
        self,
        pos0: ArrayLike,
        vel0: ArrayLike = (0.0, 0.0),
        depth0: float = 0.0,
        depth_rate0: float = 0.0,
        cfg: HybridFusionConfig | None = None,
        initial_mode: NavMode = NavMode.SURFACE,
    ) -> None:
        """Initialize the filter from horizontal position, velocity, and depth."""
        self.cfg = cfg or HybridFusionConfig()
        self.mode_mgr = ModeManager(self.cfg.mode, initial=initial_mode)
        pos = self._vector2(pos0, name="pos0")
        vel = self._vector2(vel0, name="vel0")
        depth = float(depth0)
        if not np.isfinite(depth) or depth < 0.0:
            raise ValueError("depth0 must be finite and non-negative")
        depth_rate = float(depth_rate0)
        if not np.isfinite(depth_rate):
            raise ValueError("depth_rate0 must be finite")
        self._x = np.zeros(self.N, dtype=float)
        self._x[self.POS] = pos
        self._x[self.DEPTH] = depth
        self._x[self.DEPTH_RATE] = depth_rate
        self._x[self.VEL] = vel
        p = np.zeros(self.N)
        p[self.POS] = self.cfg.init_pos_std**2
        p[self.DEPTH] = self.cfg.init_depth_std**2
        p[self.VEL] = self.cfg.init_vel_std**2
        p[self.DEPTH_RATE] = self.cfg.init_depth_rate_std**2
        p[self.BIAS] = self.cfg.init_bias_std**2
        self._P = np.diag(p)
        self._t = 0.0
        self._last_packet_timestamp_s: float | None = None
        self._last_gps_t: float | None = None
        self._last_bathy_t: float | None = None
        self._last_aiding_t: dict[str, float] = {}
        self._rejections: deque[FusionRejection] = deque(
            maxlen=self.cfg.rejection_history_size
        )
        self._total_rejections = 0
        self._bathy_confidence = 1.0
        self._bathy_trusted = True
        self._degradation_level = NavDegradationLevel.NOMINAL
        self._consecutive_bathy_failures = 0

    @property
    def t(self) -> float:
        """Current filter time in seconds."""
        return self._t

    @property
    def state_vector(self) -> FloatArray:
        """Return a read-only copy of the complete 8D state vector."""
        value = self._x.copy()
        value.setflags(write=False)
        return value

    @property
    def covariance(self) -> FloatArray:
        """Return a read-only copy of the 8×8 covariance."""
        value = self._P.copy()
        value.setflags(write=False)
        return value

    @property
    def rejections(self) -> tuple[FusionRejection, ...]:
        """Return the bounded innovation-rejection history."""
        return tuple(self._rejections)

    def step(self, packet: SensorPacket) -> HybridNavState:
        """Process one sensor packet and return the resulting estimate."""
        self._validate_packet_timestamp(packet)
        if packet.imu is not None and packet.imu.quality.available:
            self.predict(packet.imu)

        depth_for_mode = self._x[self.DEPTH]
        if (
            packet.depth is not None
            and packet.depth.quality.available
            and np.isfinite(packet.depth.depth_m)
        ):
            depth_for_mode = float(packet.depth.depth_m)
        mode = self.mode_mgr.update(depth_m=depth_for_mode, hint=packet.mode_hint)

        if packet.velocity is not None:
            self.update_velocity(packet.velocity)
        if packet.depth is not None:
            self.update_depth(packet.depth)
        if packet.bathymetry is not None and mode == NavMode.SUBMERGED:
            if packet.bathy_health is not None:
                self._apply_bathy_health(packet.bathy_health)
            if (
                self._bathy_trusted
                and self._degradation_level != NavDegradationLevel.FAULT
            ):
                if self.update_bathymetry(packet.bathymetry):
                    self._last_bathy_t = self._t
                    self._consecutive_bathy_failures = 0
                else:
                    self._consecutive_bathy_failures += 1
            elif packet.bathymetry is not None:
                self._consecutive_bathy_failures += 1
        elif packet.bathy_health is not None:
            self._apply_bathy_health(packet.bathy_health)
        if packet.gps is not None and mode == NavMode.SURFACE:
            if self.update_gps(packet.gps):
                self._last_gps_t = self._t

        return self.state()

    def predict(self, imu: ImuMeasurement) -> None:
        """Propagate the state and covariance with one horizontal IMU sample."""
        dt = float(imu.dt)
        accel = np.asarray(imu.accel, dtype=float)
        self._t += dt
        a = accel - self._x[self.BIAS]
        self._x[self.POS] += self._x[self.VEL] * dt + 0.5 * a * dt * dt
        next_depth = self._x[self.DEPTH] + self._x[self.DEPTH_RATE] * dt
        self._x[self.DEPTH] = max(float(next_depth), 0.0)
        if next_depth < 0.0:
            self._x[self.DEPTH_RATE] = 0.0
        tau = self.cfg.depth_rate_tau_s
        depth_rate_decay = float(np.exp(-dt / tau))
        self._x[self.DEPTH_RATE] *= depth_rate_decay
        self._x[self.VEL] += a * dt

        F = np.eye(self.N)
        F[self.POS, self.VEL] = np.eye(2) * dt
        F[self.POS, self.BIAS] = -0.5 * dt * dt * np.eye(2)
        F[self.DEPTH, self.DEPTH_RATE] = dt
        F[self.VEL, self.BIAS] = -dt * np.eye(2)

        q_a = (self.cfg.accel_noise * max(imu.quality.scale, 1e-6)) ** 2
        q_z_acc = self.cfg.depth_rate_noise**2
        q_z_rw = self.cfg.depth_process_noise**2
        q_b = self.cfg.accel_bias_rw**2
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
        self._P = self._stabilize_cov(F @ self._P @ F.T + Q)

    def update_depth(self, meas: DepthMeasurement) -> bool:
        """Fuse a pressure/depth measurement; return whether it was accepted."""
        if not meas.quality.available or not np.isfinite(meas.depth_m):
            return False
        value = float(meas.depth_m)
        if meas.timestamp_s is not None:
            lag = self._t - float(meas.timestamp_s)
            if lag > 1e-9:
                value += float(self._x[self.DEPTH_RATE]) * lag
        return self._update_linear(
            np.array([value]),
            meas.quality.apply(np.array([[float(meas.var)]])),
            [self.DEPTH],
            self.cfg.depth_gate_chi2,
            "depth",
        )

    def update_gps(self, gps: GpsMeasurement) -> bool:
        """Fuse GPS position and optional velocity; return acceptance status."""
        if not gps.quality.available:
            return False
        pos = np.asarray(gps.pos, dtype=float)
        if gps.timestamp_s is not None and float(gps.timestamp_s) < self._t - 1e-9:
            pos = compensate_measurement_latency(
                pos,
                self._x[self.VEL],
                measurement_time_s=float(gps.timestamp_s),
                filter_time_s=self._t,
            )
        ok_pos = self._update_linear(
            pos,
            gps.quality.apply(gps.pos_cov),
            [0, 1],
            self.cfg.gps_gate_chi2,
            "gps_pos",
        )
        ok_vel = False
        if gps.vel is not None:
            vel = np.asarray(gps.vel, dtype=float)
            if gps.timestamp_s is not None and float(gps.timestamp_s) < self._t - 1e-9:
                vel = compensate_measurement_latency(
                    vel,
                    np.zeros(2),
                    measurement_time_s=float(gps.timestamp_s),
                    filter_time_s=self._t,
                )
            cov = gps.vel_cov if gps.vel_cov is not None else np.diag([0.15, 0.15]) ** 2
            ok_vel = self._update_linear(
                vel,
                gps.quality.apply(cov),
                [3, 4],
                self.cfg.velocity_gate_chi2,
                "gps_vel",
            )
        return ok_pos or ok_vel

    def update_velocity(self, vel: VelocityMeasurement) -> bool:
        """Fuse a DVL-style horizontal velocity measurement."""
        if not vel.quality.available:
            return False
        velocity = np.asarray(vel.vel, dtype=float)
        if vel.timestamp_s is not None and float(vel.timestamp_s) < self._t - 1e-9:
            velocity = compensate_measurement_latency(
                velocity,
                np.zeros(2),
                measurement_time_s=float(vel.timestamp_s),
                filter_time_s=self._t,
            )
        return self._update_linear(
            velocity,
            vel.quality.apply(vel.cov),
            [3, 4],
            self.cfg.velocity_gate_chi2,
            "velocity",
        )

    def update_bathymetry(self, meas: BathymetryMeasurement) -> bool:
        """Fuse a bathymetry-derived horizontal position observation."""
        if not meas.quality.available:
            return False
        pos, cov = meas.as_position_fix()
        if meas.timestamp_s is not None and float(meas.timestamp_s) < self._t - 1e-9:
            pos = compensate_measurement_latency(
                pos,
                self._x[self.VEL],
                measurement_time_s=float(meas.timestamp_s),
                filter_time_s=self._t,
            )
        if self._degradation_level != NavDegradationLevel.NOMINAL:
            cov = (
                np.asarray(cov, dtype=float)
                * (1.0 / max(self._bathy_confidence, 0.25)) ** 2
            )
        return self._update_linear(
            pos,
            cov,
            [0, 1],
            self.cfg.bathy_gate_chi2,
            "bathymetry",
        )

    def _update_linear(
        self,
        z: ArrayLike,
        R: ArrayLike,
        idx: list[int],
        gate: float,
        source: str,
    ) -> bool:
        z = np.asarray(z, dtype=float)
        R = np.asarray(R, dtype=float)
        expected = (len(idx),)
        if z.shape != expected or R.shape != (len(idx), len(idx)):
            raise ValueError("measurement and covariance dimensions do not match")
        if not np.all(np.isfinite(z)) or not np.all(np.isfinite(R)):
            raise ValueError("measurement and covariance must be finite")
        if not np.allclose(R, R.T, atol=1e-10):
            raise ValueError("measurement covariance must be symmetric")
        if np.any(np.diag(R) <= 0.0) or np.linalg.eigvalsh(R).min() < -1e-10:
            raise ValueError("measurement covariance must be positive semidefinite")
        R = self._stabilize_cov(R)
        H = np.zeros((len(idx), self.N))
        for row, col in enumerate(idx):
            H[row, col] = 1.0
        y = z - H @ self._x
        S = self._stabilize_cov(H @ self._P @ H.T + R)
        nis = float(y @ np.linalg.solve(S, y))
        if not np.isfinite(nis) or nis > gate:
            self._record_rejection(source, nis, gate)
            return False
        K = np.linalg.solve(S, H @ self._P).T
        self._x = self._x + K @ y
        identity = np.eye(self.N)
        A = identity - K @ H
        self._P = self._stabilize_cov(A @ self._P @ A.T + K @ R @ K.T)
        self._enforce_physical_state()
        self._last_aiding_t[self._aiding_group(source)] = self._t
        return True

    def state(self) -> HybridNavState:
        """Return a copy of the current state and covariance."""
        recent = tuple(
            rejection
            for rejection in self._rejections
            if self._t - rejection.t <= self.cfg.health_window_s
        )
        aiding = frozenset(
            source
            for source, accepted_t in self._last_aiding_t.items()
            if self._t - accepted_t <= self.cfg.aiding_timeout_s
        )
        healthy = (
            np.all(np.isfinite(self._x))
            and np.all(np.isfinite(self._P))
            and np.linalg.eigvalsh(self._P).min() >= -self.cfg.min_cov
            and np.sqrt(max(np.linalg.eigvalsh(self._P[0:2, 0:2]).max(), 0.0))
            <= self.cfg.max_position_std_m
            and len(recent) <= self.cfg.max_recent_rejections
            and self._degradation_level != NavDegradationLevel.FAULT
        )
        if self._consecutive_bathy_failures >= 3:
            self._degradation_level = NavDegradationLevel.DEGRADED
        elif (
            self._degradation_level == NavDegradationLevel.DEGRADED
            and self._bathy_trusted
            and self._consecutive_bathy_failures == 0
            and len(recent) <= max(1, self.cfg.max_recent_rejections // 2)
        ):
            self._degradation_level = NavDegradationLevel.NOMINAL
        if not healthy and self._degradation_level == NavDegradationLevel.NOMINAL:
            self._degradation_level = NavDegradationLevel.DEGRADED
        if (
            not np.all(np.isfinite(self._x))
            or np.sqrt(max(np.linalg.eigvalsh(self._P[0:2, 0:2]).max(), 0.0))
            > self.cfg.max_position_std_m * 2.0
        ):
            self._degradation_level = NavDegradationLevel.FAULT
        return HybridNavState(
            pos=self._x[self.POS],
            vel=self._x[self.VEL],
            cov=self._P,
            mode=self.mode_mgr.mode,
            t=self._t,
            depth_m=float(self._x[self.DEPTH]),
            depth_rate_mps=float(self._x[self.DEPTH_RATE]),
            last_gps_t=self._last_gps_t,
            last_bathy_t=self._last_bathy_t,
            diagnostics=FusionDiagnostics(
                filter_healthy=bool(healthy),
                total_rejections=self._total_rejections,
                recent_rejections=recent,
                aiding_sources=aiding,
                degradation_level=self._degradation_level,
                bathy_confidence=float(self._bathy_confidence),
                bathy_trusted=bool(self._bathy_trusted),
            ),
        )

    def reset(
        self,
        pos: ArrayLike,
        vel: ArrayLike | None = None,
        pos_cov: ArrayLike | None = None,
        depth_m: float | None = None,
    ) -> HybridNavState:
        """Re-anchor state blocks and clear their stale cross-covariances.

        Horizontal velocity covariance is reinitialized even when ``vel`` is
        omitted. Supplying ``depth_m`` also zeros depth rate and resets the
        coupled depth/depth-rate covariance block.
        """
        self._x[self.POS] = self._vector2(pos, name="pos")
        position_cov = (
            self._covariance2(pos_cov, name="pos_cov")
            if pos_cov is not None
            else np.diag([self.cfg.init_pos_std] * 2) ** 2
        )
        self._reset_block([0, 1], position_cov)
        if vel is not None:
            self._x[self.VEL] = self._vector2(vel, name="vel")
        self._reset_block([3, 4], np.diag([self.cfg.init_vel_std] * 2) ** 2)
        if depth_m is not None:
            depth = float(depth_m)
            if not np.isfinite(depth) or depth < 0.0:
                raise ValueError("depth_m must be finite and non-negative")
            self._x[self.DEPTH] = depth
            self._x[self.DEPTH_RATE] = 0.0
            self._reset_block(
                [self.DEPTH, self.DEPTH_RATE],
                np.diag([self.cfg.init_depth_std, self.cfg.init_depth_rate_std]) ** 2,
            )
        self._P = self._stabilize_cov(self._P)
        return self.state()

    def _reset_block(self, idx: list[int], cov: ArrayLike) -> None:
        self._P[idx, :] = 0.0
        self._P[:, idx] = 0.0
        self._P[np.ix_(idx, idx)] = self._stabilize_cov(cov)

    def _validate_packet_timestamp(self, packet: SensorPacket) -> None:
        timestamp = packet.timestamp_s
        if timestamp is None:
            return
        if (
            self._last_packet_timestamp_s is not None
            and timestamp < self._last_packet_timestamp_s - 1e-9
        ):
            raise ValueError("sensor packet timestamps must be monotonic")
        self._last_packet_timestamp_s = timestamp

    def _apply_bathy_health(self, health: MatchHealth) -> None:
        self._bathy_confidence = float(health.confidence)
        self._bathy_trusted = bool(health.trusted)
        if health.degraded:
            self._degradation_level = NavDegradationLevel.DEGRADED

    def _record_rejection(self, source: str, nis: float, gate: float) -> None:
        self._total_rejections += 1
        self._rejections.append(FusionRejection(self._t, source, nis, gate))

    def _enforce_physical_state(self) -> None:
        if self._x[self.DEPTH] < 0.0:
            self._x[self.DEPTH] = 0.0
            self._x[self.DEPTH_RATE] = max(self._x[self.DEPTH_RATE], 0.0)

    @staticmethod
    def _aiding_group(source: str) -> str:
        return "gps" if source.startswith("gps_") else source

    @staticmethod
    def _vector2(value: ArrayLike, *, name: str) -> FloatArray:
        vector = np.asarray(value, dtype=float)
        if vector.shape != (2,) or not np.all(np.isfinite(vector)):
            raise ValueError(f"{name} must be a finite 2-vector")
        return vector

    @staticmethod
    def _covariance2(value: ArrayLike, *, name: str) -> FloatArray:
        covariance = np.asarray(value, dtype=float)
        if covariance.shape != (2, 2) or not np.all(np.isfinite(covariance)):
            raise ValueError(f"{name} must be a finite 2x2 matrix")
        if not np.allclose(covariance, covariance.T, atol=1e-10):
            raise ValueError(f"{name} must be symmetric")
        if (
            np.any(np.diag(covariance) <= 0.0)
            or np.linalg.eigvalsh(covariance).min() < -1e-10
        ):
            raise ValueError(f"{name} must be positive semidefinite")
        return covariance

    def _stabilize_cov(self, M: ArrayLike) -> FloatArray:
        M = self._sym(np.asarray(M, dtype=float))
        w, V = np.linalg.eigh(M)
        w = np.maximum(w, self.cfg.min_cov)
        return self._sym((V * w) @ V.T)

    @staticmethod
    def _sym(M: FloatArray) -> FloatArray:
        return 0.5 * (M + M.T)
