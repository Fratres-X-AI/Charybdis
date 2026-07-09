"""Public API for the primary surface/submerged UUV navigation stack.

Import hardware-neutral measurements, fusion, mode management, and patrol
types from this package. Implementation helpers remain in their modules.
"""

from __future__ import annotations

from .bathymetry import (
    BathymetryMap,
    BathymetryMatch,
    BathymetryProfile,
    MatchStatus,
    TerrainMatcherConfig,
    TerrainProfileMatcher,
)
from .fusion import (
    FusionDiagnostics,
    FusionRejection,
    HybridFusionConfig,
    HybridNavState,
    HybridSensorFusion,
)
from .modes import ModeManager, ModeManagerConfig, NavMode
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
    "BathymetryMatch",
    "MatchStatus",
    "TerrainMatcherConfig",
    "TerrainProfileMatcher",
    "ModeManager",
    "ModeManagerConfig",
    "SensorQuality",
    "ImuMeasurement",
    "GpsMeasurement",
    "DepthMeasurement",
    "VelocityMeasurement",
    "BathymetryMeasurement",
    "SensorPacket",
    "HybridFusionConfig",
    "FusionRejection",
    "FusionDiagnostics",
    "HybridNavState",
    "HybridSensorFusion",
    "HybridNavigator",
    "HybridStepResult",
    "Waypoint",
    "PatrolRoute",
    "PatrolCommand",
    "PatrolExecutor",
]
