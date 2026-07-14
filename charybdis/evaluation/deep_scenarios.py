"""Named deep-ocean scenarios (1-1000 m) and release gates."""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..hybrid.fusion import HybridFusionConfig
from ..hybrid.modes import NavMode
from ..hybrid.patrol import PatrolRoute
from ..simulation.deep import HybridDeepConfig, _deep_wp, _default_fusion_config

DEEP_VALIDATION_SCENARIOS = (
    "deep_nominal",
    "deep_midwater",
    "deep_1000m",
    "deep_dvl_dropout",
    "deep_sparse_bathymetry",
    "deep_steady_current",
    "deep_long_blackout",
)


@dataclass(frozen=True)
class DeepValidationGates:
    """Pre-declared release limits for one deep-ocean scenario."""

    max_cep95_m: float
    max_depth_cep95_m: float
    min_route_completion_rate: float = 0.88
    min_healthy_rate: float = 0.88
    max_divergence_rate: float = 0.08
    max_gps_reacquisition_jump_m: float = 25.0


def build_deep_validation_scenario(name: str) -> HybridDeepConfig:
    """Return a deterministic configuration for a named deep scenario."""
    if name == "deep_nominal":
        return HybridDeepConfig(name=name)
    if name == "deep_midwater":
        return HybridDeepConfig(
            name=name,
            max_steps=2400,
            route=_midwater_route(),
        )
    if name == "deep_1000m":
        return HybridDeepConfig(
            name=name,
            max_steps=2400,
            route=_max_depth_route(),
        )
    if name == "deep_dvl_dropout":
        return HybridDeepConfig(
            name=name,
            max_steps=2400,
            velocity_dropout_steps=(180, 260),
        )
    if name == "deep_sparse_bathymetry":
        return HybridDeepConfig(
            name=name,
            max_steps=2400,
            bathy_period_steps=16,
            bathy_dropout_steps=(240, 320),
            bathy_outlier_steps=(200, 216),
            bathy_outlier_m=18.0,
        )
    if name == "deep_steady_current":
        return HybridDeepConfig(
            name=name,
            max_steps=2400,
            current_xy_mps=(0.12, -0.08),
        )
    if name == "deep_long_blackout":
        return HybridDeepConfig(
            name=name,
            max_steps=2800,
            route=_long_blackout_route(),
            gps_dropout_steps=(120, 2720),
            fusion=_long_blackout_fusion_config(),
        )
    choices = ", ".join(DEEP_VALIDATION_SCENARIOS)
    raise ValueError(
        f"unknown deep validation scenario {name!r}; choose from {choices}"
    )


def deep_validation_gates(name: str) -> DeepValidationGates:
    """Return scenario-specific gates fixed before deep validation runs."""
    if name not in DEEP_VALIDATION_SCENARIOS:
        build_deep_validation_scenario(name)
    if name == "deep_nominal":
        return DeepValidationGates(max_cep95_m=42.0, max_depth_cep95_m=3.0)
    if name == "deep_midwater":
        return DeepValidationGates(max_cep95_m=48.0, max_depth_cep95_m=4.0)
    if name == "deep_1000m":
        return DeepValidationGates(
            max_cep95_m=58.0,
            max_depth_cep95_m=5.0,
            min_route_completion_rate=0.85,
            max_gps_reacquisition_jump_m=35.0,
        )
    if name == "deep_dvl_dropout":
        return DeepValidationGates(max_cep95_m=55.0, max_depth_cep95_m=4.5)
    if name == "deep_sparse_bathymetry":
        return DeepValidationGates(max_cep95_m=60.0, max_depth_cep95_m=5.0)
    if name == "deep_long_blackout":
        return DeepValidationGates(
            max_cep95_m=62.0,
            max_depth_cep95_m=5.5,
            min_route_completion_rate=0.85,
            max_gps_reacquisition_jump_m=30.0,
        )
    return DeepValidationGates(max_cep95_m=52.0, max_depth_cep95_m=4.5)


def _midwater_route() -> PatrolRoute:
    return PatrolRoute(
        (
            _deep_wp([0.0, 0.0], mode=NavMode.SURFACE, speed_mps=1.6, radius_m=10.0),
            _deep_wp([200.0, 0.0], mode=NavMode.SUBMERGED, depth_m=200.0),
            _deep_wp([300.0, 0.0], mode=NavMode.SURFACE, speed_mps=1.4, radius_m=16.0),
            _deep_wp([365.0, 0.0], mode=NavMode.SUBMERGED, depth_m=500.0),
            _deep_wp([400.0, 0.0], mode=NavMode.SURFACE, speed_mps=1.4, radius_m=16.0),
            _deep_wp([480.0, 0.0], mode=NavMode.SUBMERGED, depth_m=500.0),
            _deep_wp(
                [360.0, 120.0], mode=NavMode.SURFACE, speed_mps=1.4, radius_m=22.0
            ),
        )
    )


def _max_depth_route() -> PatrolRoute:
    return PatrolRoute(
        (
            _deep_wp([0.0, 0.0], mode=NavMode.SURFACE, speed_mps=1.6, radius_m=10.0),
            _deep_wp([165.0, 0.0], mode=NavMode.SUBMERGED, depth_m=200.0),
            _deep_wp([365.0, 0.0], mode=NavMode.SUBMERGED, depth_m=500.0),
            _deep_wp(
                [717.0, 0.0], mode=NavMode.SUBMERGED, depth_m=1000.0, speed_mps=1.2
            ),
            _deep_wp(
                [360.0, 120.0], mode=NavMode.SURFACE, speed_mps=1.5, radius_m=22.0
            ),
        )
    )


def _long_blackout_route() -> PatrolRoute:
    """Surface start, long submerged transit, terminal surface GPS recovery."""
    return PatrolRoute(
        (
            _deep_wp([0.0, 0.0], mode=NavMode.SURFACE, speed_mps=1.6, radius_m=10.0),
            _deep_wp([120.0, 0.0], mode=NavMode.SUBMERGED, depth_m=180.0),
            _deep_wp([520.0, 0.0], mode=NavMode.SUBMERGED, depth_m=350.0),
            _deep_wp([900.0, 0.0], mode=NavMode.SUBMERGED, depth_m=420.0),
            _deep_wp([980.0, 0.0], mode=NavMode.SURFACE, speed_mps=1.4, radius_m=18.0),
            _deep_wp(
                [860.0, 140.0], mode=NavMode.SURFACE, speed_mps=1.4, radius_m=22.0
            ),
        )
    )


def _long_blackout_fusion_config() -> HybridFusionConfig:
    base = _default_fusion_config()
    return replace(base, aiding_timeout_s=900.0, max_recent_rejections=400)


__all__ = [
    "DEEP_VALIDATION_SCENARIOS",
    "DeepValidationGates",
    "build_deep_validation_scenario",
    "deep_validation_gates",
]
