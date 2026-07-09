"""Convenience API for the primary surface/submerged UUV navigation stack.

The package root exposes only the smallest integration surface. This subpackage
adds the common construction and inspection types needed by examples and SDK
users. Lower-level diagnostics and implementation helpers remain available from
their defining modules.
"""

from __future__ import annotations

from .bathymetry import (
    BathymetryMap,
    BathymetryProfile,
    MatchStatus,
    TerrainMatcherConfig,
    TerrainProfileMatcher,
)
from .fusion import (
    HybridFusionConfig,
    HybridNavState,
    HybridSensorFusion,
)
from .modes import NavMode
from .navigator import HybridNavigator, HybridStepResult
from .patrol import PatrolCommand, PatrolExecutor, PatrolRoute, Waypoint
from .sensors import (
    BathymetryMeasurement,
    DepthMeasurement,
    GpsMeasurement,
    ImuMeasurement,
    SensorPacket,
    SensorQuality,
    VelocityMeasurement,
)

__all__ = [
    "NavMode",
    "BathymetryMap",
    "BathymetryProfile",
    "MatchStatus",
    "TerrainMatcherConfig",
    "TerrainProfileMatcher",
    "SensorQuality",
    "ImuMeasurement",
    "GpsMeasurement",
    "DepthMeasurement",
    "VelocityMeasurement",
    "BathymetryMeasurement",
    "SensorPacket",
    "HybridFusionConfig",
    "HybridNavState",
    "HybridSensorFusion",
    "HybridNavigator",
    "HybridStepResult",
    "Waypoint",
    "PatrolRoute",
    "PatrolCommand",
    "PatrolExecutor",
]
