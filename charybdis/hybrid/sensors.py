"""Abstract sensor inputs for hybrid UUV navigation.

These dataclasses describe measurements, not hardware. Real drivers, simulators,
or log replayers can populate them without changing the fusion code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .modes import NavMode

FloatArray = NDArray[np.float64]


def _readonly_array(
    value: ArrayLike, *, name: str, shape: tuple[int, ...]
) -> FloatArray:
    a = np.array(value, dtype=np.float64, copy=True)
    if a.shape != shape or not np.all(np.isfinite(a)):
        raise ValueError(f"{name} must be a finite array with shape {shape}")
    a.setflags(write=False)
    return a


def _vec2(value: ArrayLike, *, name: str = "value") -> FloatArray:
    return _readonly_array(value, name=name, shape=(2,))


def _cov2(value: ArrayLike, *, name: str) -> FloatArray:
    cov = _readonly_array(value, name=name, shape=(2, 2))
    if not np.allclose(cov, cov.T, atol=1e-10):
        raise ValueError(f"{name} must be symmetric")
    if np.any(np.diag(cov) <= 0.0) or np.linalg.eigvalsh(cov).min() < -1e-10:
        raise ValueError(f"{name} must be positive semidefinite with positive diagonal")
    return cov


def _positive(value: float, *, name: str, allow_zero: bool = False) -> float:
    result = float(value)
    if not np.isfinite(result) or (result < 0.0 if allow_zero else result <= 0.0):
        relation = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{name} must be finite and {relation}")
    return result


def _timestamp(value: float | None) -> float | None:
    if value is None:
        return None
    return _positive(value, name="timestamp_s", allow_zero=True)


@dataclass(frozen=True)
class SensorQuality:
    """Availability plus confidence multiplier.

    ``scale`` inflates covariance: 1.0 is nominal, 2.0 means half as trusted.
    """

    available: bool = True
    scale: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.available, bool):
            raise TypeError("available must be bool")
        object.__setattr__(self, "scale", _positive(self.scale, name="scale"))

    def apply(self, cov: ArrayLike) -> FloatArray:
        """Inflate a covariance matrix by this quality scale."""
        return np.asarray(cov, dtype=float) * self.scale**2


@dataclass(frozen=True)
class ImuMeasurement:
    """Horizontal specific force over one prediction interval."""

    accel: ArrayLike
    dt: float
    quality: SensorQuality = field(default_factory=SensorQuality)
    timestamp_s: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "accel", _vec2(self.accel, name="accel"))
        object.__setattr__(self, "dt", _positive(self.dt, name="dt"))
        object.__setattr__(self, "timestamp_s", _timestamp(self.timestamp_s))


@dataclass(frozen=True)
class GpsMeasurement:
    """Surface GPS position with optional horizontal velocity."""

    pos: ArrayLike
    vel: ArrayLike | None = None
    pos_cov: ArrayLike = field(default_factory=lambda: np.diag([3.0, 3.0]) ** 2)
    vel_cov: ArrayLike | None = None
    quality: SensorQuality = field(default_factory=SensorQuality)
    timestamp_s: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "pos", _vec2(self.pos, name="pos"))
        object.__setattr__(self, "pos_cov", _cov2(self.pos_cov, name="pos_cov"))
        if self.vel is not None:
            object.__setattr__(self, "vel", _vec2(self.vel, name="vel"))
            if self.vel_cov is not None:
                object.__setattr__(self, "vel_cov", _cov2(self.vel_cov, name="vel_cov"))
        elif self.vel_cov is not None:
            raise ValueError("vel_cov requires vel")
        object.__setattr__(self, "timestamp_s", _timestamp(self.timestamp_s))


@dataclass(frozen=True)
class DepthMeasurement:
    """Positive-down pressure depth observation in metres."""

    depth_m: float
    var: float = 0.5**2
    quality: SensorQuality = field(default_factory=SensorQuality)
    timestamp_s: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "depth_m", _positive(self.depth_m, name="depth_m", allow_zero=True)
        )
        object.__setattr__(self, "var", _positive(self.var, name="var"))
        object.__setattr__(self, "timestamp_s", _timestamp(self.timestamp_s))


@dataclass(frozen=True)
class VelocityMeasurement:
    """DVL-style horizontal velocity observation."""

    vel: ArrayLike
    cov: ArrayLike = field(default_factory=lambda: np.diag([0.08, 0.08]) ** 2)
    quality: SensorQuality = field(default_factory=SensorQuality)
    timestamp_s: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "vel", _vec2(self.vel, name="vel"))
        object.__setattr__(self, "cov", _cov2(self.cov, name="cov"))
        object.__setattr__(self, "timestamp_s", _timestamp(self.timestamp_s))


@dataclass(frozen=True)
class BathymetryMeasurement:
    """Terrain/bathymetry aiding as either a position fix or feature observation.

    For a feature observation, ``bearing_rad`` is the nav-frame bearing from the
    vehicle to the mapped feature.
    """

    pos_fix: ArrayLike | None = None
    pos_cov: ArrayLike | None = None
    feature_pos: ArrayLike | None = None
    range_m: float | None = None
    bearing_rad: float | None = None
    range_var: float = 2.0**2
    bearing_var: float = np.deg2rad(3.0) ** 2
    feature_cov: ArrayLike = field(default_factory=lambda: np.diag([5.0, 5.0]) ** 2)
    quality: SensorQuality = field(default_factory=SensorQuality)
    timestamp_s: float | None = None

    def __post_init__(self) -> None:
        has_fix = self.pos_fix is not None
        has_feature = any(
            value is not None
            for value in (self.feature_pos, self.range_m, self.bearing_rad)
        )
        if has_fix == has_feature:
            raise ValueError("provide exactly one of pos_fix or feature range/bearing")
        if self.pos_fix is not None:
            object.__setattr__(self, "pos_fix", _vec2(self.pos_fix, name="pos_fix"))
            if self.pos_cov is not None:
                object.__setattr__(self, "pos_cov", _cov2(self.pos_cov, name="pos_cov"))
        else:
            if (
                self.feature_pos is None
                or self.range_m is None
                or self.bearing_rad is None
            ):
                raise ValueError(
                    "feature observation requires feature_pos, range_m, and bearing_rad"
                )
            object.__setattr__(
                self, "feature_pos", _vec2(self.feature_pos, name="feature_pos")
            )
            object.__setattr__(
                self,
                "range_m",
                _positive(self.range_m, name="range_m", allow_zero=True),
            )
            bearing = float(self.bearing_rad)
            if not np.isfinite(bearing):
                raise ValueError("bearing_rad must be finite")
            object.__setattr__(self, "bearing_rad", bearing)
            object.__setattr__(
                self, "range_var", _positive(self.range_var, name="range_var")
            )
            object.__setattr__(
                self, "bearing_var", _positive(self.bearing_var, name="bearing_var")
            )
            object.__setattr__(
                self, "feature_cov", _cov2(self.feature_cov, name="feature_cov")
            )
        object.__setattr__(self, "timestamp_s", _timestamp(self.timestamp_s))

    def as_position_fix(self) -> tuple[FloatArray, FloatArray]:
        """Convert either representation into a position and covariance."""
        if self.pos_fix is not None:
            cov = (
                self.pos_cov if self.pos_cov is not None else np.diag([15.0, 15.0]) ** 2
            )
            return np.asarray(self.pos_fix, dtype=float), self.quality.apply(cov)

        if self.feature_pos is None or self.range_m is None or self.bearing_rad is None:
            raise ValueError(
                "bathymetry measurement needs pos_fix or feature range/bearing"
            )

        r = float(self.range_m)
        th = float(self.bearing_rad)
        u = np.array([np.cos(th), np.sin(th)])
        feature_pos = cast(FloatArray, self.feature_pos)
        pos = feature_pos - r * u
        j = np.array(
            [
                [-np.cos(th), r * np.sin(th)],
                [-np.sin(th), -r * np.cos(th)],
            ]
        )
        cov_rb = np.diag([self.range_var, self.bearing_var])
        cov = j @ cov_rb @ j.T + np.asarray(self.feature_cov, dtype=float)
        return pos, self.quality.apply(cov)


@dataclass(frozen=True)
class SensorPacket:
    """Measurements and optional mode hint processed in one fusion cycle."""

    imu: ImuMeasurement | None = None
    gps: GpsMeasurement | None = None
    depth: DepthMeasurement | None = None
    velocity: VelocityMeasurement | None = None
    bathymetry: BathymetryMeasurement | None = None
    mode_hint: NavMode | None = None
    timestamp_s: float | None = None

    def __post_init__(self) -> None:
        packet_time = _timestamp(self.timestamp_s)
        object.__setattr__(self, "timestamp_s", packet_time)
        if packet_time is None:
            return
        for measurement in (
            self.imu,
            self.gps,
            self.depth,
            self.velocity,
            self.bathymetry,
        ):
            measurement_time = None if measurement is None else measurement.timestamp_s
            if measurement_time is not None and measurement_time > packet_time + 1e-9:
                raise ValueError("measurement timestamp cannot exceed packet timestamp")
