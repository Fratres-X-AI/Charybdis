"""Power budget configuration and step updates."""

from __future__ import annotations

from dataclasses import replace

from charybdis.hybrid.power import PowerBudgetConfig


def default_mission_power() -> PowerBudgetConfig:
    """Baseline mission budget: cruise discharge only."""
    return PowerBudgetConfig(enabled=True, endurance_s=5400.0)


def solar_recharge_power(*, endurance_s: float = 5400.0) -> PowerBudgetConfig:
    """Surface solar/GPS sniff recharge profile."""
    return PowerBudgetConfig(
        enabled=True,
        endurance_s=endurance_s,
        surface_charge=0.45,
    )


def hydrokinetic_harvest_power(*, endurance_s: float = 5400.0) -> PowerBudgetConfig:
    """Foil/prop flow-harvest profile with harvest drag penalty."""
    return PowerBudgetConfig(
        enabled=True,
        endurance_s=endurance_s,
        hydro_charge_coeff=0.07,
        hydro_drag_coeff=0.018,
    )


def harbor_recharge_power(*, endurance_s: float = 4800.0) -> PowerBudgetConfig:
    """Staged harbor exit with strong surface recharge legs."""
    return replace(
        solar_recharge_power(endurance_s=endurance_s),
        surface_charge=0.50,
    )


__all__ = [
    "PowerBudgetConfig",
    "default_mission_power",
    "harbor_recharge_power",
    "hydrokinetic_harvest_power",
    "solar_recharge_power",
]
