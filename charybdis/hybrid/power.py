"""Normalized battery budget for hybrid harbor and deep simulations."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PowerBudgetConfig:
    """Per-step energy model using normalized loads and an endurance timescale.

    Discharge rate is expressed in units where ``hotel_load + propulsion_coeff``
    equals full cruise at ``reference_speed_mps``. Dividing net discharge by
    ``endurance_s`` maps one second at that load to a fractional state-of-charge
    drop. Charging sources subtract from net discharge (solar on surface, hydro
    harvest when submerged).
    """

    enabled: bool = False
    initial_energy_frac: float = 1.0
    reference_speed_mps: float = 1.5
    hotel_load: float = 0.30
    propulsion_coeff: float = 0.70
    bathy_ping_load: float = 0.15
    surface_charge: float = 0.0
    hydro_charge_coeff: float = 0.0
    hydro_drag_coeff: float = 0.0
    endurance_s: float = 7200.0
    rtb_frac: float = 0.20
    min_energy_frac: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise TypeError("enabled must be bool")
        if not 0.0 < self.initial_energy_frac <= 1.0:
            raise ValueError("initial_energy_frac must be in (0, 1]")
        positive = {
            "reference_speed_mps": self.reference_speed_mps,
            "endurance_s": self.endurance_s,
        }
        non_negative = {
            "hotel_load": self.hotel_load,
            "propulsion_coeff": self.propulsion_coeff,
            "bathy_ping_load": self.bathy_ping_load,
            "surface_charge": self.surface_charge,
            "hydro_charge_coeff": self.hydro_charge_coeff,
            "hydro_drag_coeff": self.hydro_drag_coeff,
            "min_energy_frac": self.min_energy_frac,
        }
        for name, value in positive.items():
            if not np.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        for name, value in non_negative.items():
            if not np.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
        if not 0.0 <= self.rtb_frac <= 1.0:
            raise ValueError("rtb_frac must be in [0, 1]")
        if self.min_energy_frac > self.initial_energy_frac:
            raise ValueError("min_energy_frac cannot exceed initial_energy_frac")


@dataclass
class PowerBudgetState:
    """Mutable state tracked across simulation steps."""

    energy_frac: float
    rtb_triggered: bool = False
    energy_depleted: bool = False


def init_power_state(cfg: PowerBudgetConfig) -> PowerBudgetState | None:
    """Return initial energy state when the budget is enabled."""
    if not cfg.enabled:
        return None
    return PowerBudgetState(energy_frac=float(cfg.initial_energy_frac))


def step_power_budget(
    state: PowerBudgetState,
    cfg: PowerBudgetConfig,
    *,
    speed_mps: float,
    depth_m: float,
    surface_depth_m: float,
    submerged: bool,
    bathy_ping: bool,
    current_xy_mps: tuple[float, float],
    dt_s: float,
    surfaced: bool | None = None,
) -> None:
    """Advance the battery by one step given motion and sensor activity."""
    speed = max(float(speed_mps), 0.0)
    speed_frac = (
        speed / cfg.reference_speed_mps if cfg.reference_speed_mps > 0.0 else 0.0
    )
    discharge = cfg.hotel_load + cfg.propulsion_coeff * speed_frac**3
    if bathy_ping:
        discharge += cfg.bathy_ping_load

    charge = 0.0
    on_surface = surfaced if surfaced is not None else depth_m <= surface_depth_m
    if on_surface and cfg.surface_charge > 0.0:
        charge += cfg.surface_charge
    if submerged and cfg.hydro_charge_coeff > 0.0:
        flow_mps = speed + float(np.hypot(*current_xy_mps))
        charge += cfg.hydro_charge_coeff * flow_mps
        discharge += cfg.hydro_drag_coeff * flow_mps

    net_discharge = discharge - charge
    delta = net_discharge * dt_s / cfg.endurance_s
    state.energy_frac = float(
        np.clip(
            state.energy_frac - delta,
            cfg.min_energy_frac,
            1.0,
        )
    )
    if state.energy_frac <= cfg.rtb_frac and not state.rtb_triggered:
        state.rtb_triggered = True
    if state.energy_frac <= cfg.min_energy_frac:
        state.energy_depleted = True


def power_summary(
    history: tuple[float, ...],
    state: PowerBudgetState | None,
) -> dict[str, float | bool]:
    """Return JSON-compatible power metrics for a completed run."""
    if state is None or not history:
        return {}
    return {
        "final_energy_frac": float(history[-1]),
        "min_energy_frac": float(min(history)),
        "rtb_triggered": bool(state.rtb_triggered),
        "energy_depleted": bool(state.energy_depleted),
    }


__all__ = [
    "PowerBudgetConfig",
    "PowerBudgetState",
    "init_power_state",
    "power_summary",
    "step_power_budget",
]
