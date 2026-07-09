"""Abstract sensor inputs for hybrid UUV navigation.

These dataclasses describe measurements, not hardware. Real drivers, simulators,
or log replayers can populate them without changing the fusion code.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np

from .modes import NavMode


def _vec2(v) -> np.ndarray:
    a = np.asarray(v, dtype=float)
    if a.shape != (2,):
        raise ValueError("expected a 2-vector")
    return a


@dataclass(frozen=True)
class SensorQuality:
    """Availability plus confidence multiplier.

    ``scale`` inflates covariance: 1.0 is nominal, 2.0 means half as trusted.
    """

    available: bool = True
    scale: float = 1.0

    def apply(self, cov: np.ndarray) -> np.ndarray:
        return np.asarray(cov, dtype=float) * max(float(self.scale), 1e-6) ** 2


@dataclass(frozen=True)
class ImuMeasurement:
    accel: np.ndarray
    dt: float
    quality: SensorQuality = field(default_factory=SensorQuality)

    def __post_init__(self):
        object.__setattr__(self, "accel", _vec2(self.accel))


@dataclass(frozen=True)
class GpsMeasurement:
    pos: np.ndarray
    vel: np.ndarray | None = None
    pos_cov: np.ndarray = field(default_factory=lambda: np.diag([3.0, 3.0]) ** 2)
    vel_cov: np.ndarray | None = None
    quality: SensorQuality = field(default_factory=SensorQuality)

    def __post_init__(self):
        object.__setattr__(self, "pos", _vec2(self.pos))
        if self.vel is not None:
            object.__setattr__(self, "vel", _vec2(self.vel))


@dataclass(frozen=True)
class DepthMeasurement:
    depth_m: float
    var: float = 0.5 ** 2
    quality: SensorQuality = field(default_factory=SensorQuality)


@dataclass(frozen=True)
class VelocityMeasurement:
    vel: np.ndarray
    cov: np.ndarray = field(default_factory=lambda: np.diag([0.08, 0.08]) ** 2)
    quality: SensorQuality = field(default_factory=SensorQuality)

    def __post_init__(self):
        object.__setattr__(self, "vel", _vec2(self.vel))


@dataclass(frozen=True)
class BathymetryMeasurement:
    """Terrain/bathymetry aiding as either a position fix or feature observation.

    For a feature observation, ``bearing_rad`` is the nav-frame bearing from the
    vehicle to the mapped feature.
    """

    pos_fix: np.ndarray | None = None
    pos_cov: np.ndarray | None = None
    feature_pos: np.ndarray | None = None
    range_m: float | None = None
    bearing_rad: float | None = None
    range_var: float = 2.0 ** 2
    bearing_var: float = np.deg2rad(3.0) ** 2
    feature_cov: np.ndarray = field(default_factory=lambda: np.diag([5.0, 5.0]) ** 2)
    quality: SensorQuality = field(default_factory=SensorQuality)

    def __post_init__(self):
        if self.pos_fix is not None:
            object.__setattr__(self, "pos_fix", _vec2(self.pos_fix))
        if self.feature_pos is not None:
            object.__setattr__(self, "feature_pos", _vec2(self.feature_pos))

    def as_position_fix(self) -> tuple[np.ndarray, np.ndarray]:
        if self.pos_fix is not None:
            cov = self.pos_cov if self.pos_cov is not None else np.diag([15.0, 15.0]) ** 2
            return self.pos_fix, self.quality.apply(cov)

        if self.feature_pos is None or self.range_m is None or self.bearing_rad is None:
            raise ValueError("bathymetry measurement needs pos_fix or feature range/bearing")

        r = float(self.range_m)
        th = float(self.bearing_rad)
        u = np.array([np.cos(th), np.sin(th)])
        pos = self.feature_pos - r * u
        j = np.array([
            [-np.cos(th), r * np.sin(th)],
            [-np.sin(th), -r * np.cos(th)],
        ])
        cov_rb = np.diag([self.range_var, self.bearing_var])
        cov = j @ cov_rb @ j.T + np.asarray(self.feature_cov, dtype=float)
        return pos, self.quality.apply(cov)


@dataclass(frozen=True)
class SensorPacket:
    imu: ImuMeasurement | None = None
    gps: GpsMeasurement | None = None
    depth: DepthMeasurement | None = None
    velocity: VelocityMeasurement | None = None
    bathymetry: BathymetryMeasurement | None = None
    mode_hint: NavMode | None = None
