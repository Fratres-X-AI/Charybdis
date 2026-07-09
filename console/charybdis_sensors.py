"""High-fidelity DVL + IMU sensor models for Charybdis.

Doppler Velocity Log (Janus configuration): four slanted acoustic beams at a
fixed angle from vertical, 90 deg apart in azimuth. Each beam measures the
along-beam Doppler projection of the seabed-relative velocity. We reconstruct
the 2-D horizontal velocity by least squares from the good beams, so the model
naturally captures:

  * per-beam white noise,
  * a multiplicative velocity scale-factor error (sound-speed miscalibration),
  * beam dropout over bad bottom (fewer beams -> degraded / rank-deficient fix).

The IMU contributes a slowly walking heading (attitude) bias that rotates the
body-frame DVL velocity when it is resolved into the navigation frame - the
dominant real-world dead-reckoning error - plus a residual velocity bias.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

BEAM_TILT_DEG = 30.0
BEAM_AZ_DEG = np.array([45.0, 135.0, 225.0, 315.0])


@dataclass
class DvlReading:
    velocity: np.ndarray     # estimated seabed-relative velocity (nav frame) [2]
    quality: float           # 0..1 (fraction of good beams, 0 if unusable)
    n_good: int


def _beam_unit_vectors() -> np.ndarray:
    """Horizontal projections of the four Janus beam directions (unit-ish)."""
    tilt = np.deg2rad(BEAM_TILT_DEG)
    az = np.deg2rad(BEAM_AZ_DEG)
    sh = np.sin(tilt)
    return np.stack([sh * np.cos(az), sh * np.sin(az)], axis=1)  # [4,2]


_BEAMS = _beam_unit_vectors()


def dvl_beam_measure(true_vel: np.ndarray, params, rng: np.random.Generator
                     ) -> DvlReading:
    """Simulate the Janus DVL and reconstruct horizontal velocity."""
    beam_noise = max(params.dvl, 0.0) * 0.05
    scale = 1.0 + rng.normal(0.0, getattr(params, "dvl_scale", 0.01))
    dropout_p = getattr(params, "dvl_dropout", 0.0)

    proj = _BEAMS @ np.asarray(true_vel, float) * scale
    proj = proj + rng.normal(0.0, beam_noise, size=4)
    good = rng.random(4) >= dropout_p
    n_good = int(good.sum())

    if n_good < 3:
        # Bottom-lock lost: no usable velocity this tick.
        return DvlReading(velocity=np.asarray(true_vel, float).copy(),
                          quality=0.0, n_good=n_good)

    A = _BEAMS[good]
    b = proj[good]
    vel, *_ = np.linalg.lstsq(A, b, rcond=None)
    return DvlReading(velocity=vel, quality=n_good / 4.0, n_good=n_good)


def imu_heading_bias_walk(bias_rad: float, params, rng: np.random.Generator
                          ) -> float:
    """Random-walk the IMU heading (yaw) bias [rad]."""
    std = np.deg2rad(0.02 * max(params.drift, 0.0))
    return bias_rad + rng.normal(0.0, std)


def rotate(vec: np.ndarray, angle_rad: float) -> np.ndarray:
    c, s = np.cos(angle_rad), np.sin(angle_rad)
    return np.array([c * vec[0] - s * vec[1], s * vec[0] + c * vec[1]])


def imu_velocity_bias_walk(bias: np.ndarray, params, rng: np.random.Generator
                           ) -> np.ndarray:
    """Advance the residual velocity (accelerometer) bias random walk."""
    std = 0.002 * max(params.drift, 0.0)
    return bias + rng.normal(0.0, std, size=2)
