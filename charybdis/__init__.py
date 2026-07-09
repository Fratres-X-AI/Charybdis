"""Stable hybrid UUV navigation API.

Legacy interceptor and experimental research APIs require explicit subpackage
imports and are never loaded by importing :mod:`charybdis`.
"""

from __future__ import annotations

from .hybrid import (
    BathymetryMap,
    HybridNavigator,
    HybridNavState,
    HybridSensorFusion,
    HybridStepResult,
    NavMode,
    PatrolExecutor,
    SensorPacket,
    TerrainProfileMatcher,
)
from .version import __version__

__all__ = [
    "__version__",
    "BathymetryMap",
    "NavMode",
    "SensorPacket",
    "HybridNavState",
    "HybridSensorFusion",
    "HybridNavigator",
    "HybridStepResult",
    "PatrolExecutor",
    "TerrainProfileMatcher",
]
