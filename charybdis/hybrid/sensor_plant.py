"""Stateful high-fidelity sensor corruption for hybrid simulation."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from .frames import apply_timing_jitter, body_to_nav, wrap_pi
from .sensors import (
    DepthMeasurement,
    GpsMeasurement,
    ImuMeasurement,
    VelocityMeasurement,
)

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class SensorPlantConfig:
    """Realistic IMU, depth, GPS, and DVL error parameters."""

    imu_accel_bias0_mps2: tuple[float, float] = (0.012, -0.009)
    imu_accel_bias_rw_mps2_sqrt_s: float = 0.00045
    imu_accel_noise_mps2: float = 0.008
    imu_heading_bias0_rad: float = np.deg2rad(0.35)
    imu_heading_bias_rw_rad_sqrt_s: float = np.deg2rad(0.015)
    depth_noise_m: float = 0.25
    depth_lag_tau_s: float = 2.5
    depth_rate_noise_mps: float = 0.015
    gps_noise_m: float = 2.5
    gps_vel_noise_mps: float = 0.1
    gps_outlier_prob: float = 0.0015
    gps_outlier_scale_m: float = 75.0
    dvl_noise_mps: float = 0.06
    timing_jitter_s: float = 0.04
    seed: int = 0

    def __post_init__(self) -> None:
        positive = (
            "imu_accel_bias_rw_mps2_sqrt_s",
            "imu_accel_noise_mps2",
            "imu_heading_bias_rw_rad_sqrt_s",
            "depth_noise_m",
            "depth_lag_tau_s",
            "depth_rate_noise_mps",
            "gps_noise_m",
            "gps_vel_noise_mps",
            "gps_outlier_scale_m",
            "dvl_noise_mps",
            "timing_jitter_s",
        )
        for name in positive:
            value = float(getattr(self, name))
            if not np.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
        if not 0.0 <= float(self.gps_outlier_prob) <= 1.0:
            raise ValueError("gps_outlier_prob must be in [0, 1]")
        bias0 = tuple(float(value) for value in self.imu_accel_bias0_mps2)
        if len(bias0) != 2 or not np.all(np.isfinite(bias0)):
            raise ValueError("imu_accel_bias0_mps2 must contain two finite values")
        if not isinstance(self.seed, int):
            raise TypeError("seed must be int")


@dataclass
class SensorPlantState:
    """Persistent sensor error states carried across simulation steps."""

    accel_bias: FloatArray = field(default_factory=lambda: np.zeros(2))
    heading_bias_rad: float = 0.0
    depth_filtered_m: float = 0.0
    depth_initialized: bool = False


class SensorPlant:
    """Generate corrupted measurements from ground-truth vehicle state."""

    def __init__(
        self,
        cfg: SensorPlantConfig | None = None,
        *,
        rng: np.random.Generator | None = None,
    ) -> None:
        self.cfg = cfg or SensorPlantConfig()
        self.rng = rng or np.random.default_rng(self.cfg.seed)
        self.state = SensorPlantState(
            accel_bias=np.asarray(self.cfg.imu_accel_bias0_mps2, dtype=np.float64),
            heading_bias_rad=float(self.cfg.imu_heading_bias0_rad),
        )

    def advance(self, dt: float) -> None:
        """Random-walk IMU biases over one interval."""
        step = float(dt)
        if not np.isfinite(step) or step <= 0.0:
            raise ValueError("dt must be finite and positive")
        rw = self.cfg.imu_accel_bias_rw_mps2_sqrt_s * np.sqrt(step)
        self.state.accel_bias = self.state.accel_bias + self.rng.normal(0.0, rw, size=2)
        heading_rw = self.cfg.imu_heading_bias_rw_rad_sqrt_s * np.sqrt(step)
        self.state.heading_bias_rad = wrap_pi(
            self.state.heading_bias_rad + float(self.rng.normal(0.0, heading_rw))
        )

    def imu(
        self,
        true_accel_nav: FloatArray,
        *,
        dt: float,
        timestamp_s: float,
    ) -> ImuMeasurement:
        """Return a navigation-frame IMU sample with bias, noise, and jitter."""
        self.advance(dt)
        corrupted = (
            np.asarray(true_accel_nav, dtype=np.float64)
            - self.state.accel_bias
            + self.rng.normal(0.0, self.cfg.imu_accel_noise_mps2, size=2)
        )
        meas_time = apply_timing_jitter(
            timestamp_s,
            self.rng,
            jitter_std_s=self.cfg.timing_jitter_s,
        )
        return ImuMeasurement(
            corrupted,
            dt=dt,
            timestamp_s=meas_time,
        )

    def depth(
        self,
        true_depth_m: float,
        *,
        dt: float,
        timestamp_s: float,
    ) -> DepthMeasurement:
        """Return a lagged, noisy pressure-depth observation."""
        step = float(dt)
        depth = float(true_depth_m)
        if not self.state.depth_initialized:
            self.state.depth_filtered_m = depth
            self.state.depth_initialized = True
        alpha = min(step / max(self.cfg.depth_lag_tau_s, step), 1.0)
        self.state.depth_filtered_m += (depth - self.state.depth_filtered_m) * alpha
        noisy = self.state.depth_filtered_m + float(
            self.rng.normal(0.0, self.cfg.depth_noise_m)
        )
        rate_noise = self.rng.normal(0.0, self.cfg.depth_rate_noise_mps) * step
        measured = max(noisy + rate_noise, 0.0)
        meas_time = apply_timing_jitter(
            timestamp_s,
            self.rng,
            jitter_std_s=self.cfg.timing_jitter_s,
        )
        variance = (
            self.cfg.depth_noise_m**2 + (self.cfg.depth_rate_noise_mps * step) ** 2
        )
        return DepthMeasurement(
            measured,
            var=max(float(variance), 1e-6),
            timestamp_s=meas_time,
        )

    def gps(
        self,
        true_pos: FloatArray,
        true_vel: FloatArray,
        *,
        timestamp_s: float,
    ) -> GpsMeasurement:
        """Return a GPS fix with white noise and occasional heavy-tail outliers."""
        pos = np.asarray(true_pos, dtype=np.float64) + self.rng.normal(
            0.0, self.cfg.gps_noise_m, size=2
        )
        vel = np.asarray(true_vel, dtype=np.float64) + self.rng.normal(
            0.0, self.cfg.gps_vel_noise_mps, size=2
        )
        if self.rng.random() < self.cfg.gps_outlier_prob:
            direction = self.rng.normal(0.0, 1.0, size=2)
            norm = float(np.linalg.norm(direction))
            if norm > 1e-9:
                direction /= norm
            pos = pos + direction * self.cfg.gps_outlier_scale_m
        meas_time = apply_timing_jitter(
            timestamp_s,
            self.rng,
            jitter_std_s=self.cfg.timing_jitter_s,
        )
        return GpsMeasurement(
            pos,
            vel=vel,
            pos_cov=np.diag([self.cfg.gps_noise_m] * 2) ** 2,
            vel_cov=np.diag([self.cfg.gps_vel_noise_mps] * 2) ** 2,
            timestamp_s=meas_time,
        )

    def dvl(
        self,
        true_vel_nav: FloatArray,
        heading_rad: float,
        *,
        timestamp_s: float,
    ) -> VelocityMeasurement:
        """Return a DVL velocity with body-frame noise mapped into navigation."""
        body_noise = self.rng.normal(0.0, self.cfg.dvl_noise_mps, size=2)
        nav_noise = body_to_nav(body_noise, heading_rad)
        measured = np.asarray(true_vel_nav, dtype=np.float64) + nav_noise
        meas_time = apply_timing_jitter(
            timestamp_s,
            self.rng,
            jitter_std_s=self.cfg.timing_jitter_s,
        )
        return VelocityMeasurement(
            measured,
            cov=np.diag([self.cfg.dvl_noise_mps] * 2) ** 2,
            timestamp_s=meas_time,
        )


__all__ = ["SensorPlant", "SensorPlantConfig", "SensorPlantState"]
