"""Action authority envelope: what the vehicle is still permitted to do.

Localization can remain operational while evidence for the next action has
degraded. This module maps nav/evidence signals to continuous permission scores.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .config import SimConfig
from .legacy.navigator import Navigator
from .pcrb import terrain_fisher_information
from .terrain import Terrain

ACTIONS = ("transit", "terrain_fix", "hold", "rtb", "go_dark", "active_acoustic")


def _clip01(x: float) -> float:
    return float(np.clip(x, 0.0, 1.0))


def _nav_score(terrain: Terrain, cfg: SimConfig, pos: np.ndarray) -> float:
    R = cfg.radar_noise ** 2 + cfg.baro_noise ** 2
    J = terrain_fisher_information(terrain, float(pos[0]), float(pos[1]), R)
    w = np.linalg.eigvalsh(J)
    # scale: ~0.02 weak, ~0.15 strong on synthetic tiles
    return _clip01(float(np.sqrt(max(w[-1], 0.0))) / 0.12)


def _recent_trn_health(nav: Navigator, window: int = 12) -> tuple[float, float]:
    """Return (accept_rate, mean_nis) over recent TRN updates."""
    rec = nav.rec.trn_nis[-window:]
    if not rec:
        return 1.0, 1.0
    acc = sum(1 for _, _, ok in rec if ok) / len(rec)
    nis = float(np.mean([n for _, n, _ in rec]))
    return acc, nis


@dataclass(frozen=True)
class ActionEnvelope:
    """Continuous permission scores in [0, 1] for each action class."""
    permitted: dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0          # overall authority to act
    binding: str = "none"            # dominant limiting factor
    pos_err_1sigma: float = 0.0
    nav_score: float = 0.0
    filter_spread_m: float = 0.0
    trn_accept_rate: float = 1.0

    def allows(self, action: str, threshold: float = 0.5) -> bool:
        return self.permitted.get(action, 0.0) >= threshold

    def best_action(self, threshold: float = 0.5) -> str | None:
        ok = [(a, s) for a, s in self.permitted.items() if s >= threshold]
        if not ok:
            return None
        return max(ok, key=lambda x: x[1])[0]


def compute_action_envelope(
    nav: Navigator,
    terrain: Terrain,
    *,
    t: float | None = None,
    threat: float = 0.0,
    map_trust: float = 1.0,
) -> ActionEnvelope:
    """Jointly score admissible actions from nav/evidence (not binary fallback).

    ``threat`` in [0, 3]: 0 benign, 3 heavily contested.
    ``map_trust`` in [0, 1]: 1 fresh/trusted map, 0 stale/spoofed.
    """
    cfg = nav.cfg
    est = nav.estimate("auto", t=t)
    pos = est.pos
    err_r = est.error_radius_1sigma
    nav_s = _nav_score(terrain, cfg, pos)
    acc, mean_nis = _recent_trn_health(nav)

    # Filter spread: disagreement between available estimators.
    spreads = []
    ekf_p = nav.ekf.pos
    if nav.pf is not None:
        spreads.append(float(np.linalg.norm(nav.pf.pos - ekf_p)))
    if nav.pmf is not None:
        spreads.append(float(np.linalg.norm(nav.pmf.pos - ekf_p)))
    spread = max(spreads) if spreads else 0.0

    ins_drift = float(np.linalg.norm(nav.ins.pos - ekf_p))

    # Evidence scalars (1 = good).
    uncert = _clip01(1.0 - err_r / 250.0)
    innov = _clip01(1.0 - (mean_nis - 1.0) / 8.0)
    accept = _clip01(acc)
    terrain_ok = _clip01(0.35 * nav_s + 0.65 * map_trust)
    agree = _clip01(1.0 - spread / 180.0)
    drift = _clip01(1.0 - ins_drift / 400.0)
    threat_ok = _clip01(1.0 - threat / 3.0)

    neff_ok = 1.0
    if nav.pf is not None:
        neff_ok = _clip01(nav.pf.neff() / max(0.35 * nav.pf.N, 1.0))

    confidence = _clip01(
        0.25 * uncert + 0.20 * innov + 0.15 * accept
        + 0.15 * terrain_ok + 0.15 * agree + 0.10 * drift
    )

    permitted = {
        "transit": _clip01(confidence * (0.6 + 0.4 * terrain_ok)),
        "terrain_fix": _clip01(min(uncert, terrain_ok, accept, innov) * (0.5 + 0.5 * nav_s)),
        "hold": _clip01(0.4 + 0.6 * (1.0 - uncert)),
        "rtb": _clip01(0.3 + 0.7 * (1.0 - confidence)),
        "go_dark": _clip01(threat_ok * (0.5 + 0.5 * (1.0 - accept))),
        "active_acoustic": _clip01(
            min(uncert, innov) * (1.0 - nav_s) * neff_ok * threat_ok
        ),
    }

    # Binding factor: weakest link among primary drivers.
    drivers = {
        "uncertainty": uncert,
        "innovation": innov,
        "trn_rejects": accept,
        "terrain": terrain_ok,
        "filter_divergence": agree,
        "ins_drift": drift,
        "threat": threat_ok,
    }
    binding = min(drivers, key=drivers.get)

    return ActionEnvelope(
        permitted=permitted,
        confidence=confidence,
        binding=binding,
        pos_err_1sigma=err_r,
        nav_score=nav_s,
        filter_spread_m=spread,
        trn_accept_rate=acc,
    )
