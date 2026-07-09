"""Public API for the primary surface/submerged UUV navigation stack.

Import hardware-neutral measurements, fusion, mode management, and patrol
types from this package. Implementation helpers remain in their modules.
"""
from __future__ import annotations

from .fusion import HybridFusionConfig, HybridNavState, HybridSensorFusion
from .modes import ModeManager, ModeManagerConfig, NavMode
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
    "HybridNavState",
    "HybridSensorFusion",
    "Waypoint",
    "PatrolRoute",
    "PatrolCommand",
    "PatrolExecutor",
]
