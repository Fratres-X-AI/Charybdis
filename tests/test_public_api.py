"""Snapshot tests for the deliberate public API surface."""

from __future__ import annotations

import charybdis
import charybdis.evaluation as evaluation
import charybdis.hybrid as hybrid


def test_root_public_api_is_minimal_and_stable() -> None:
    assert charybdis.__all__ == [
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


def test_hybrid_convenience_api_is_explicit_and_stable() -> None:
    assert hybrid.__all__ == [
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
        "PowerBudgetConfig",
        "PowerBudgetState",
    ]


def test_evaluation_contract_versions_are_named_and_stable() -> None:
    assert evaluation.REPLAY_SCHEMA_VERSION == "1"
    assert evaluation.VALIDATION_ARTIFACT_SCHEMA_VERSION == "1"
