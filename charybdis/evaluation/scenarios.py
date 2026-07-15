"""Named synthetic scenarios and release gates for hybrid validation."""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..hybrid.modes import NavMode
from ..hybrid.patrol import PatrolRoute, Waypoint
from ..simulation.hybrid import (
    HybridHarborConfig,
    _default_fusion_config,
    _default_matcher_config,
)

VALIDATION_SCENARIOS = (
    "harbor_nominal",
    "long_submerge",
    "gps_dvl_dropout",
    "sparse_outlier_bathymetry",
    "steady_current",
    "large_initial_error",
    "repeated_mode_transitions",
)


@dataclass(frozen=True)
class ValidationGates:
    """Pre-declared release limits for one synthetic scenario."""

    max_cep95_m: float
    max_depth_cep95_m: float
    min_route_completion_rate: float = 0.90
    min_healthy_rate: float = 0.90
    max_divergence_rate: float = 0.06
    max_gps_reacquisition_jump_m: float = 12.0


def build_validation_scenario(name: str) -> HybridHarborConfig:
    """Return a deterministic configuration for a named validation scenario."""
    if name == "harbor_nominal":
        return HybridHarborConfig(name=name)
    if name == "long_submerge":
        return HybridHarborConfig(
            name=name,
            max_steps=480,
            route=_long_submerge_route(),
        )
    if name == "gps_dvl_dropout":
        return HybridHarborConfig(
            name=name,
            max_steps=320,
            gps_dropout_steps=(0, 25),
            velocity_dropout_steps=(30, 65),
        )
    if name == "sparse_outlier_bathymetry":
        return HybridHarborConfig(
            name=name,
            max_steps=320,
            bathy_period_steps=12,
            bathy_dropout_steps=(45, 65),
            bathy_outlier_steps=(36, 48, 72),
            bathy_outlier_m=12.0,
            fusion=replace(_default_fusion_config(), bathy_gate_chi2=16.0),
        )
    if name == "steady_current":
        return HybridHarborConfig(
            name=name,
            max_steps=360,
            current_xy_mps=(0.25, -0.15),
        )
    if name == "large_initial_error":
        return HybridHarborConfig(
            name=name,
            max_steps=320,
            initial_pos_error_xy_m=(12.0, -8.0),
        )
    if name == "repeated_mode_transitions":
        return HybridHarborConfig(
            name=name,
            max_steps=560,
            route=_repeated_transition_route(),
            use_mode_hints=True,
            matcher=replace(_default_matcher_config(), min_cost_margin=0.25),
        )
    choices = ", ".join(VALIDATION_SCENARIOS)
    raise ValueError(f"unknown validation scenario {name!r}; choose from {choices}")


def validation_gates(name: str) -> ValidationGates:
    """Return scenario-specific gates fixed before release validation runs."""
    if name not in VALIDATION_SCENARIOS:
        build_validation_scenario(name)
    if name == "harbor_nominal":
        return ValidationGates(max_cep95_m=10.0, max_depth_cep95_m=1.0)
    if name in {"long_submerge", "steady_current"}:
        return ValidationGates(max_cep95_m=22.0, max_depth_cep95_m=1.5)
    if name == "large_initial_error":
        return ValidationGates(max_cep95_m=18.0, max_depth_cep95_m=1.5)
    if name == "repeated_mode_transitions":
        return ValidationGates(
            max_cep95_m=25.0,
            max_depth_cep95_m=2.5,
            min_route_completion_rate=0.88,
        )
    return ValidationGates(max_cep95_m=25.0, max_depth_cep95_m=1.5)


def _long_submerge_route() -> PatrolRoute:
    return PatrolRoute(
        (
            Waypoint([0.0, 0.0], mode=NavMode.SURFACE, radius_m=3.0),
            Waypoint([25.0, 0.0], mode=NavMode.SURFACE, radius_m=5.0),
            Waypoint(
                [100.0, 0.0],
                mode=NavMode.SUBMERGED,
                depth_m=10.0,
                radius_m=9.0,
            ),
            Waypoint(
                [100.0, 100.0],
                mode=NavMode.SUBMERGED,
                depth_m=12.0,
                radius_m=9.0,
            ),
            Waypoint(
                [0.0, 100.0],
                mode=NavMode.SUBMERGED,
                depth_m=10.0,
                radius_m=9.0,
            ),
            Waypoint([0.0, 20.0], mode=NavMode.SURFACE, radius_m=8.0),
        )
    )


def _repeated_transition_route() -> PatrolRoute:
    return PatrolRoute(
        (
            Waypoint([0.0, 0.0], mode=NavMode.SURFACE, radius_m=3.0),
            Waypoint(
                [25.0, 0.0],
                mode=NavMode.SUBMERGED,
                depth_m=6.0,
                radius_m=9.0,
            ),
            Waypoint([45.0, 15.0], mode=NavMode.SURFACE, radius_m=9.0),
            Waypoint(
                [65.0, 30.0],
                mode=NavMode.SUBMERGED,
                depth_m=10.0,
                radius_m=9.0,
            ),
            Waypoint([35.0, 50.0], mode=NavMode.SURFACE, radius_m=9.0),
            Waypoint(
                [5.0, 30.0],
                mode=NavMode.SUBMERGED,
                depth_m=7.0,
                radius_m=9.0,
            ),
            Waypoint([0.0, 5.0], mode=NavMode.SURFACE, radius_m=9.0),
        )
    )


__all__ = [
    "VALIDATION_SCENARIOS",
    "ValidationGates",
    "build_validation_scenario",
    "validation_gates",
]
