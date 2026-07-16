"""Mission-vision scenarios for littoral insertion and long-range UUV transit.

These are characterization missions — not release gates. They model operational
patterns (shore launch, ship drop, solar sniff transits) using the same hybrid
simulation stack as integration validation.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from ..hybrid.fusion import HybridFusionConfig
from ..hybrid.modes import NavMode
from ..hybrid.patrol import PatrolRoute, Waypoint
from ..simulation.deep import HybridDeepConfig, _deep_wp, _default_fusion_config
from ..simulation.hybrid import (
    HybridHarborConfig,
)
from ..simulation.hybrid import (
    _default_fusion_config as _harbor_fusion_config,
)
from .deep_scenarios import DeepValidationGates
from .power_profiles import (
    default_mission_power,
    harbor_recharge_power,
    hydrokinetic_harvest_power,
    solar_recharge_power,
)
from .scenarios import ValidationGates

MissionDomain = Literal["harbor", "deep"]

MISSION_SCENARIOS: tuple[str, ...] = (
    "shore_beach_landing",
    "ship_to_shore_insertion",
    "shore_to_shore_transfer",
    "harbor_to_open_ocean_recharge",
    "stealth_solar_transit",
    "hydrokinetic_transit",
)

MISSION_DESCRIPTIONS: dict[str, str] = {
    "shore_beach_landing": (
        "Shore-launched UUV: surface departure, submerged littoral transit, "
        "final shallow run-in to a beach landing point (payload delivery profile)."
    ),
    "ship_to_shore_insertion": (
        "Offboard launch from a mothership: brief surface GPS fix offshore, "
        "submerged ingress through the surf zone to a shore waypoint."
    ),
    "shore_to_shore_transfer": (
        "Coastal shuttle between two shore sites with a submerged leg and GPS "
        "denial mid-transit (contested littoral handoff)."
    ),
    "harbor_to_open_ocean_recharge": (
        "Depart protected harbor, transit submerged to open water, periodic "
        "surface GPS recharge legs before continuing offshore."
    ),
    "stealth_solar_transit": (
        "Long-range stealth profile: mostly submerged with scheduled surface "
        "sniffs for solar/GPS recharge (compressed transoceanic leg spacing)."
    ),
    "hydrokinetic_transit": (
        "Fully submerged long leg with no surface exposure: models flow-harvest "
        "charging (foil/prop micro-turbines) enabling uninterrupted GPS-denied transit."
    ),
}


@dataclass(frozen=True)
class MissionScenarioSpec:
    """One named mission and its simulation domain."""

    name: str
    domain: MissionDomain
    description: str


def mission_domain(name: str) -> MissionDomain:
    """Return whether a mission runs on harbor or deep simulation."""
    if name not in MISSION_SCENARIOS:
        _raise_unknown(name)
    if name in {"stealth_solar_transit", "hydrokinetic_transit"}:
        return "deep"
    return "harbor"


def mission_spec(name: str) -> MissionScenarioSpec:
    """Return metadata for a mission scenario."""
    if name not in MISSION_SCENARIOS:
        _raise_unknown(name)
    return MissionScenarioSpec(
        name=name,
        domain=mission_domain(name),
        description=MISSION_DESCRIPTIONS[name],
    )


def build_mission_scenario(name: str) -> HybridHarborConfig | HybridDeepConfig:
    """Return a deterministic configuration for a mission-vision scenario."""
    if name == "shore_beach_landing":
        return HybridHarborConfig(
            name=name,
            max_steps=720,
            route=_shore_beach_landing_route(),
            gps_dropout_steps=(80, 420),
            use_mode_hints=True,
            power=default_mission_power(),
        )
    if name == "ship_to_shore_insertion":
        return HybridHarborConfig(
            name=name,
            max_steps=800,
            route=_ship_to_shore_route(),
            initial_pos_error_xy_m=(6.0, -4.0),
            gps_dropout_steps=(40, 520),
            use_mode_hints=True,
            power=default_mission_power(),
        )
    if name == "shore_to_shore_transfer":
        return HybridHarborConfig(
            name=name,
            max_steps=900,
            route=_shore_to_shore_route(),
            current_xy_mps=(0.18, -0.10),
            gps_dropout_steps=(120, 520),
            power=default_mission_power(),
        )
    if name == "harbor_to_open_ocean_recharge":
        return HybridHarborConfig(
            name=name,
            max_steps=960,
            route=_harbor_to_open_ocean_recharge_route(),
            use_mode_hints=True,
            fusion=replace(_harbor_fusion_config(), aiding_timeout_s=120.0),
            power=harbor_recharge_power(),
        )
    if name == "stealth_solar_transit":
        return HybridDeepConfig(
            name=name,
            max_steps=3600,
            route=_stealth_solar_transit_route(),
            gps_dropout_steps=(120, 3400),
            gps_dropout_submerged_only=True,
            fusion=_stealth_solar_fusion_config(),
            use_mode_hints=True,
            power=solar_recharge_power(endurance_s=7200.0),
        )
    if name == "hydrokinetic_transit":
        return HybridDeepConfig(
            name=name,
            max_steps=3600,
            route=_hydrokinetic_transit_route(),
            current_xy_mps=(0.15, -0.06),
            gps_dropout_steps=(0, 3600),
            gps_dropout_submerged_only=True,
            fusion=_hydrokinetic_fusion_config(),
            use_mode_hints=True,
            power=hydrokinetic_harvest_power(endurance_s=7200.0),
        )
    _raise_unknown(name)


def mission_gates(name: str) -> ValidationGates | DeepValidationGates:
    """Return mission-characterization gates (looser than release validation)."""
    if name not in MISSION_SCENARIOS:
        _raise_unknown(name)
    if name == "shore_beach_landing":
        return ValidationGates(
            max_cep95_m=35.0,
            max_depth_cep95_m=2.0,
            min_route_completion_rate=0.85,
            max_divergence_rate=0.08,
            max_gps_reacquisition_jump_m=18.0,
        )
    if name == "ship_to_shore_insertion":
        return ValidationGates(
            max_cep95_m=38.0,
            max_depth_cep95_m=2.5,
            min_route_completion_rate=0.85,
            max_divergence_rate=0.08,
            max_gps_reacquisition_jump_m=20.0,
        )
    if name == "shore_to_shore_transfer":
        return ValidationGates(
            max_cep95_m=42.0,
            max_depth_cep95_m=2.5,
            min_route_completion_rate=0.85,
            max_divergence_rate=0.09,
            max_gps_reacquisition_jump_m=22.0,
        )
    if name == "harbor_to_open_ocean_recharge":
        return ValidationGates(
            max_cep95_m=32.0,
            max_depth_cep95_m=2.0,
            min_route_completion_rate=0.88,
            max_divergence_rate=0.07,
            max_gps_reacquisition_jump_m=16.0,
        )
    if name == "stealth_solar_transit":
        return DeepValidationGates(
            max_cep95_m=68.0,
            max_depth_cep95_m=6.0,
            min_route_completion_rate=0.82,
            max_divergence_rate=0.10,
            max_gps_reacquisition_jump_m=35.0,
        )
    return DeepValidationGates(
        max_cep95_m=72.0,
        max_depth_cep95_m=6.5,
        min_route_completion_rate=0.80,
        max_divergence_rate=0.11,
        max_gps_reacquisition_jump_m=40.0,
    )


def mission_power_gates(name: str) -> dict[str, float]:
    """Optional energy characterization thresholds for mission runs."""
    if name == "hydrokinetic_transit":
        return {"min_final_energy_frac": 0.35}
    if name == "stealth_solar_transit":
        return {"min_final_energy_frac": 0.40}
    if name == "harbor_to_open_ocean_recharge":
        return {"min_final_energy_frac": 0.45}
    return {"min_final_energy_frac": 0.25}


def _wp(
    pos: list[float],
    *,
    mode: NavMode,
    depth_m: float = 0.0,
    speed_mps: float = 1.5,
    radius_m: float = 8.0,
) -> Waypoint:
    return Waypoint(
        pos,
        mode=mode,
        depth_m=depth_m,
        speed_mps=speed_mps,
        radius_m=radius_m,
    )


def _shore_beach_landing_route() -> PatrolRoute:
    """Shore launch → submerged coastal transit → beach touchdown."""
    return PatrolRoute(
        (
            _wp([0.0, 0.0], mode=NavMode.SURFACE, speed_mps=1.2, radius_m=4.0),
            _wp([12.0, 2.0], mode=NavMode.SURFACE, speed_mps=1.4, radius_m=6.0),
            _wp(
                [35.0, 8.0],
                mode=NavMode.SUBMERGED,
                depth_m=6.0,
                speed_mps=1.6,
                radius_m=10.0,
            ),
            _wp(
                [65.0, 18.0],
                mode=NavMode.SUBMERGED,
                depth_m=8.0,
                speed_mps=1.5,
                radius_m=12.0,
            ),
            _wp(
                [88.0, 28.0],
                mode=NavMode.SUBMERGED,
                depth_m=4.0,
                speed_mps=1.2,
                radius_m=10.0,
            ),
            _wp([100.0, 32.0], mode=NavMode.SURFACE, speed_mps=0.9, radius_m=8.0),
        )
    )


def _ship_to_shore_route() -> PatrolRoute:
    """Mothership drop offshore → submerged ingress → surf-zone beach fix."""
    return PatrolRoute(
        (
            _wp([0.0, 65.0], mode=NavMode.SURFACE, speed_mps=1.0, radius_m=12.0),
            _wp([18.0, 53.0], mode=NavMode.SURFACE, speed_mps=1.2, radius_m=10.0),
            _wp(
                [41.0, 35.0],
                mode=NavMode.SUBMERGED,
                depth_m=12.0,
                speed_mps=1.5,
                radius_m=14.0,
            ),
            _wp(
                [65.0, 18.0],
                mode=NavMode.SUBMERGED,
                depth_m=8.0,
                speed_mps=1.4,
                radius_m=12.0,
            ),
            _wp(
                [88.0, 6.0],
                mode=NavMode.SUBMERGED,
                depth_m=5.0,
                speed_mps=1.1,
                radius_m=10.0,
            ),
            _wp([100.0, 0.0], mode=NavMode.SURFACE, speed_mps=0.8, radius_m=8.0),
        )
    )


def _shore_to_shore_route() -> PatrolRoute:
    """Shore site A → submerged coastal leg → shore site B rendezvous."""
    return PatrolRoute(
        (
            _wp([0.0, 0.0], mode=NavMode.SURFACE, speed_mps=1.2, radius_m=5.0),
            _wp(
                [16.0, 6.0],
                mode=NavMode.SUBMERGED,
                depth_m=7.0,
                speed_mps=1.5,
                radius_m=10.0,
            ),
            _wp(
                [44.0, 16.0],
                mode=NavMode.SUBMERGED,
                depth_m=9.0,
                speed_mps=1.5,
                radius_m=12.0,
            ),
            _wp(
                [76.0, 24.0],
                mode=NavMode.SUBMERGED,
                depth_m=7.0,
                speed_mps=1.4,
                radius_m=12.0,
            ),
            _wp([100.0, 30.0], mode=NavMode.SURFACE, speed_mps=1.2, radius_m=10.0),
        )
    )


def _harbor_to_open_ocean_recharge_route() -> PatrolRoute:
    """Harbor exit with staged submerged legs and open-ocean surface recharge."""
    return PatrolRoute(
        (
            _wp([0.0, 0.0], mode=NavMode.SURFACE, speed_mps=1.2, radius_m=4.0),
            _wp(
                [8.0, 0.0],
                mode=NavMode.SUBMERGED,
                depth_m=6.0,
                speed_mps=1.5,
                radius_m=9.0,
            ),
            _wp([24.0, 0.0], mode=NavMode.SURFACE, speed_mps=1.3, radius_m=10.0),
            _wp(
                [42.0, 0.0],
                mode=NavMode.SUBMERGED,
                depth_m=10.0,
                speed_mps=1.5,
                radius_m=12.0,
            ),
            _wp([61.0, 0.0], mode=NavMode.SURFACE, speed_mps=1.2, radius_m=12.0),
            _wp(
                [81.0, 0.0],
                mode=NavMode.SUBMERGED,
                depth_m=12.0,
                speed_mps=1.4,
                radius_m=14.0,
            ),
            _wp([100.0, 0.0], mode=NavMode.SURFACE, speed_mps=1.2, radius_m=14.0),
        )
    )


def _slope_tracking_depth_m(
    x_m: float,
    *,
    agl_m: float = 150.0,
    min_depth_m: float = 60.0,
) -> float:
    """Depth along the synthetic deep slope that keeps AGL inside DVL/bathy range."""
    bottom_m = 100.0 + 1.5 * x_m
    return max(min_depth_m, bottom_m - agl_m)


def _stealth_solar_transit_route() -> PatrolRoute:
    """Compressed transoceanic profile: submerged legs + periodic surface sniffs."""
    submerged_x = (180.0, 540.0, 900.0, 1260.0, 1620.0)
    return PatrolRoute(
        (
            _deep_wp([0.0, 0.0], mode=NavMode.SURFACE, speed_mps=1.4, radius_m=12.0),
            _deep_wp(
                [submerged_x[0], 0.0],
                mode=NavMode.SUBMERGED,
                depth_m=_slope_tracking_depth_m(submerged_x[0]),
            ),
            _deep_wp([360.0, 0.0], mode=NavMode.SURFACE, speed_mps=1.2, radius_m=16.0),
            _deep_wp(
                [submerged_x[1], 0.0],
                mode=NavMode.SUBMERGED,
                depth_m=_slope_tracking_depth_m(submerged_x[1]),
            ),
            _deep_wp([720.0, 0.0], mode=NavMode.SURFACE, speed_mps=1.2, radius_m=16.0),
            _deep_wp(
                [submerged_x[2], 0.0],
                mode=NavMode.SUBMERGED,
                depth_m=_slope_tracking_depth_m(submerged_x[2]),
            ),
            _deep_wp([1080.0, 0.0], mode=NavMode.SURFACE, speed_mps=1.2, radius_m=18.0),
            _deep_wp(
                [submerged_x[3], 0.0],
                mode=NavMode.SUBMERGED,
                depth_m=_slope_tracking_depth_m(submerged_x[3]),
            ),
            _deep_wp([1440.0, 0.0], mode=NavMode.SURFACE, speed_mps=1.2, radius_m=18.0),
            _deep_wp(
                [submerged_x[4], 0.0],
                mode=NavMode.SUBMERGED,
                depth_m=_slope_tracking_depth_m(submerged_x[4]),
            ),
            _deep_wp([1800.0, 0.0], mode=NavMode.SURFACE, speed_mps=1.3, radius_m=20.0),
        )
    )


def _hydrokinetic_transit_route() -> PatrolRoute:
    """Fully submerged transit — no surface sniffs (flow-harvest endurance profile)."""
    xs = (0.0, 240.0, 480.0, 720.0, 960.0, 1200.0, 1440.0, 1680.0, 1800.0)
    speeds = (1.3, 1.4, 1.4, 1.4, 1.4, 1.4, 1.4, 1.4, 1.3)
    return PatrolRoute(
        tuple(
            _deep_wp(
                [x, 0.0],
                mode=NavMode.SUBMERGED,
                depth_m=_slope_tracking_depth_m(x),
                speed_mps=speed,
            )
            for x, speed in zip(xs, speeds, strict=True)
        )
    )


def _stealth_solar_fusion_config() -> HybridFusionConfig:
    base = _default_fusion_config()
    return replace(
        base,
        aiding_timeout_s=1200.0,
        max_recent_rejections=512,
    )


def _hydrokinetic_fusion_config() -> HybridFusionConfig:
    base = _default_fusion_config()
    return replace(
        base,
        aiding_timeout_s=1500.0,
        max_recent_rejections=500,
    )


def _raise_unknown(name: str) -> None:
    choices = ", ".join(MISSION_SCENARIOS)
    raise ValueError(f"unknown mission scenario {name!r}; choose from {choices}")


__all__ = [
    "MISSION_DESCRIPTIONS",
    "MISSION_SCENARIOS",
    "MissionDomain",
    "MissionScenarioSpec",
    "build_mission_scenario",
    "mission_domain",
    "mission_gates",
    "mission_power_gates",
    "mission_spec",
]
