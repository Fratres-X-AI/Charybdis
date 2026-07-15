"""Power budget configuration and simulation integration tests."""

from __future__ import annotations

from dataclasses import replace

import pytest
from charybdis.evaluation.mission_scenarios import build_mission_scenario
from charybdis.evaluation.power_profiles import (
    harbor_recharge_power,
    hydrokinetic_harvest_power,
)
from charybdis.hybrid.power import (
    PowerBudgetConfig,
    PowerBudgetState,
    init_power_state,
    step_power_budget,
)
from charybdis.simulation import (
    HybridDeepConfig,
    HybridHarborConfig,
    run_hybrid_deep_simulation,
    run_hybrid_harbor_simulation,
)


def test_power_budget_disabled_by_default() -> None:
    summary = run_hybrid_harbor_simulation(HybridHarborConfig(seed=3)).summary()

    assert "power_enabled" not in summary


def test_power_budget_drains_without_charging() -> None:
    state = PowerBudgetState(energy_frac=1.0)
    cfg = PowerBudgetConfig(enabled=True, endurance_s=100.0)

    for _ in range(100):
        step_power_budget(
            state,
            cfg,
            speed_mps=1.5,
            depth_m=20.0,
            surface_depth_m=1.5,
            submerged=True,
            bathy_ping=False,
            current_xy_mps=(0.0, 0.0),
            dt_s=1.0,
            surfaced=False,
        )

    assert state.energy_frac < 0.2
    assert state.rtb_triggered


def test_surface_charge_offsets_discharge() -> None:
    draining = PowerBudgetState(energy_frac=1.0)
    charging = PowerBudgetState(energy_frac=1.0)
    base = PowerBudgetConfig(enabled=True, endurance_s=1000.0)
    drain_cfg = base
    charge_cfg = replace(base, surface_charge=0.8)

    for _ in range(50):
        step_power_budget(
            draining,
            drain_cfg,
            speed_mps=1.2,
            depth_m=2.0,
            surface_depth_m=1.5,
            submerged=False,
            bathy_ping=False,
            current_xy_mps=(0.0, 0.0),
            dt_s=1.0,
            surfaced=True,
        )
        step_power_budget(
            charging,
            charge_cfg,
            speed_mps=1.2,
            depth_m=2.0,
            surface_depth_m=1.5,
            submerged=False,
            bathy_ping=False,
            current_xy_mps=(0.0, 0.0),
            dt_s=1.0,
            surfaced=True,
        )

    assert charging.energy_frac > draining.energy_frac


def test_hydrokinetic_harvest_net_positive_with_current() -> None:
    state = PowerBudgetState(energy_frac=0.6)
    cfg = hydrokinetic_harvest_power(endurance_s=3600.0)

    for _ in range(200):
        step_power_budget(
            state,
            cfg,
            speed_mps=1.3,
            depth_m=120.0,
            surface_depth_m=1.5,
            submerged=True,
            bathy_ping=False,
            current_xy_mps=(0.15, -0.06),
            dt_s=1.0,
            surfaced=False,
        )

    assert state.energy_frac > 0.6


def test_invalid_power_config_rejected() -> None:
    with pytest.raises(ValueError, match="initial_energy_frac"):
        PowerBudgetConfig(initial_energy_frac=1.5)


def test_harbor_simulation_reports_power_when_enabled() -> None:
    cfg = replace(
        HybridHarborConfig(seed=5),
        power=harbor_recharge_power(endurance_s=1200.0),
    )
    summary = run_hybrid_harbor_simulation(cfg).summary()

    assert summary["power_enabled"] is True
    assert 0.0 <= summary["final_energy_frac"] <= 1.0
    assert summary["min_energy_frac"] <= summary["final_energy_frac"]


def test_deep_mission_profiles_enable_power() -> None:
    solar = build_mission_scenario("stealth_solar_transit")
    hydro = build_mission_scenario("hydrokinetic_transit")

    assert isinstance(solar, HybridDeepConfig)
    assert isinstance(hydro, HybridDeepConfig)
    assert solar.power.enabled is True
    assert hydro.power.enabled is True
    assert solar.power.surface_charge > 0.0
    assert hydro.power.hydro_charge_coeff > 0.0


def test_mission_solar_transit_ends_with_charge_headroom() -> None:
    cfg = replace(build_mission_scenario("stealth_solar_transit"), seed=11)
    summary = run_hybrid_deep_simulation(cfg).summary()

    assert summary["power_enabled"] is True
    assert summary["final_energy_frac"] >= 0.40


def test_init_power_state_returns_none_when_disabled() -> None:
    assert init_power_state(PowerBudgetConfig(enabled=False)) is None
