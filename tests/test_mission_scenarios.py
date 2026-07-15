"""Mission-vision scenario construction and smoke tests."""

from __future__ import annotations

from dataclasses import replace

import pytest
from charybdis.evaluation.mission_scenarios import (
    MISSION_SCENARIOS,
    build_mission_scenario,
    mission_domain,
    mission_gates,
    mission_spec,
)
from charybdis.hybrid.modes import NavMode
from charybdis.simulation import HybridDeepConfig, HybridHarborConfig
from charybdis.simulation.deep import run_hybrid_deep_simulation
from charybdis.simulation.hybrid import run_hybrid_harbor_simulation


def test_all_mission_scenarios_build_with_matching_names() -> None:
    configs = [build_mission_scenario(name) for name in MISSION_SCENARIOS]

    assert [config.name for config in configs] == list(MISSION_SCENARIOS)
    assert all(config.max_steps >= 240 for config in configs)


def test_unknown_mission_scenario_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown mission scenario"):
        build_mission_scenario("not-a-mission")


@pytest.mark.parametrize(
    ("name", "domain"),
    [
        ("shore_beach_landing", "harbor"),
        ("ship_to_shore_insertion", "harbor"),
        ("shore_to_shore_transfer", "harbor"),
        ("harbor_to_open_ocean_recharge", "harbor"),
        ("stealth_solar_transit", "deep"),
        ("hydrokinetic_transit", "deep"),
    ],
)
def test_mission_domain_classification(name: str, domain: str) -> None:
    assert mission_domain(name) == domain
    assert mission_spec(name).domain == domain


def test_hydrokinetic_transit_is_fully_submerged_gps_denied() -> None:
    config = build_mission_scenario("hydrokinetic_transit")
    assert isinstance(config, HybridDeepConfig)
    assert config.gps_dropout_steps == (0, 3600)
    assert config.gps_dropout_submerged_only is True
    assert config.power.enabled is True
    assert config.power.hydro_charge_coeff > 0.0
    assert all(
        waypoint.mode == NavMode.SUBMERGED for waypoint in config.route.waypoints
    )


def test_harbor_missions_do_not_use_deep_only_gps_fields() -> None:
    for name in MISSION_SCENARIOS:
        if mission_domain(name) != "harbor":
            continue
        config = build_mission_scenario(name)
        assert isinstance(config, HybridHarborConfig)
        assert not hasattr(config, "gps_dropout_submerged_only")


def test_mission_gates_exist_for_every_scenario() -> None:
    for name in MISSION_SCENARIOS:
        gates = mission_gates(name)
        assert gates.max_cep95_m > 0.0
        assert gates.min_route_completion_rate > 0.0


@pytest.mark.parametrize("name", ("shore_beach_landing", "hydrokinetic_transit"))
def test_mission_preview_smoke(name: str) -> None:
    config = replace(build_mission_scenario(name), seed=3)
    if mission_domain(name) == "harbor":
        summary = run_hybrid_harbor_simulation(config).summary()
    else:
        summary = run_hybrid_deep_simulation(config).summary()
    assert "final_error_m" in summary
    assert "route_complete" in summary
