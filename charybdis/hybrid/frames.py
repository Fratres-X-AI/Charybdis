"""Local navigation frame conventions and timing helpers.

Conventions (tested, do not change without updating tests):

- Horizontal: local ENU tangent plane, metres (x = East, y = North).
- Vertical: depth positive down from the surface datum (pressure depth).
- Body frame: x = surge forward, y = starboard; heading ψ measured from East,
  positive counter-clockwise (standard aviation/marine ENU yaw).
- Hybrid IMU: horizontal specific force expressed in the navigation frame.
- DVL: horizontal velocity in the navigation frame (bottom-lock assumed valid).
- GPS: horizontal position and velocity in the navigation frame.
- Bathymetry profiles: ``offsets_xy_m`` are navigation-frame East/North offsets
  from the vehicle reference point; ``bottom_depth_m`` is positive down.

Timing:

- Every ``SensorPacket`` carries ``timestamp_s`` (filter time when fused).
- Individual measurements may carry earlier ``timestamp_s`` values representing
  sensor latency. Fusion compensates small lags with a constant-velocity
  extrapolation before forming innovations.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]

# Documented axis indices for ENU horizontal vectors.
EAST = 0
NORTH = 1


def wrap_pi(angle: float) -> float:
    """Wrap an angle to [-pi, pi)."""
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def rotation_nav_to_body(heading_rad: float) -> FloatArray:
    """Return the 2×2 rotation from navigation frame to body frame."""
    heading = wrap_pi(float(heading_rad))
    cosine = np.cos(heading)
    sine = np.sin(heading)
    return np.array([[cosine, sine], [-sine, cosine]], dtype=np.float64)


def rotation_body_to_nav(heading_rad: float) -> FloatArray:
    """Return the 2×2 rotation from body frame to navigation frame."""
    heading = wrap_pi(float(heading_rad))
    cosine = np.cos(heading)
    sine = np.sin(heading)
    return np.array([[cosine, -sine], [sine, cosine]], dtype=np.float64)


def body_to_nav(vector_body: ArrayLike, heading_rad: float) -> FloatArray:
    """Rotate a 2-vector from body frame into navigation frame."""
    vector = np.asarray(vector_body, dtype=np.float64)
    if vector.shape != (2,) or not np.all(np.isfinite(vector)):
        raise ValueError("vector_body must be a finite 2-vector")
    return rotation_body_to_nav(heading_rad) @ vector


def nav_to_body(vector_nav: ArrayLike, heading_rad: float) -> FloatArray:
    """Rotate a 2-vector from navigation frame into body frame."""
    vector = np.asarray(vector_nav, dtype=np.float64)
    if vector.shape != (2,) or not np.all(np.isfinite(vector)):
        raise ValueError("vector_nav must be a finite 2-vector")
    return rotation_nav_to_body(heading_rad) @ vector


def compensate_measurement_latency(
    value: ArrayLike,
    velocity: ArrayLike,
    *,
    measurement_time_s: float,
    filter_time_s: float,
) -> FloatArray:
    """Extrapolate a delayed horizontal measurement to the current filter time."""
    vector = np.asarray(value, dtype=np.float64)
    vel = np.asarray(velocity, dtype=np.float64)
    if vector.shape != (2,) or vel.shape != (2,):
        raise ValueError("value and velocity must be 2-vectors")
    if not np.all(np.isfinite(vector)) or not np.all(np.isfinite(vel)):
        raise ValueError("value and velocity must be finite")
    if not np.isfinite(measurement_time_s) or not np.isfinite(filter_time_s):
        raise ValueError("timestamps must be finite")
    lag = filter_time_s - measurement_time_s
    if lag < -1e-9:
        raise ValueError("measurement timestamp cannot exceed filter time")
    if lag <= 1e-12:
        return vector.copy()
    return vector + vel * lag


def apply_timing_jitter(
    nominal_time_s: float,
    rng: np.random.Generator,
    *,
    jitter_std_s: float,
) -> float:
    """Return a measurement timestamp with zero-mean timing jitter."""
    nominal = float(nominal_time_s)
    std = float(jitter_std_s)
    if not np.isfinite(nominal) or nominal < 0.0:
        raise ValueError("nominal_time_s must be finite and non-negative")
    if not np.isfinite(std) or std < 0.0:
        raise ValueError("jitter_std_s must be finite and non-negative")
    if std == 0.0:
        return nominal
    delayed = nominal - abs(float(rng.normal(0.0, std)))
    return max(delayed, 0.0)


__all__ = [
    "EAST",
    "NORTH",
    "apply_timing_jitter",
    "body_to_nav",
    "compensate_measurement_latency",
    "nav_to_body",
    "rotation_body_to_nav",
    "rotation_nav_to_body",
    "wrap_pi",
]
