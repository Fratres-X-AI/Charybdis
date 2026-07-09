"""Posterior Cramér-Rao bound and terrain navigability analysis.

Computes recursive position PCRB along a truth trajectory (Tichavsky form),
terrain Fisher information / navigability maps, and filter-efficiency metrics
relative to the theoretical bound.
"""

from __future__ import annotations

import numpy as np

from .config import SimConfig
from .simulation import SimResult
from .terrain import Terrain
from .trajectory import Trajectory

N = 6  # [px, py, vx, vy, bax, bay]


def terrain_fisher_information(
    terrain: Terrain, x: float, y: float, R: float
) -> np.ndarray:
    """2-D position Fisher information for one terrain-elevation measurement."""
    g = terrain.gradient(x, y)
    return np.outer(g, g) / R


def navigability_map(
    terrain: Terrain, cfg: SimConfig, step: float | None = None
) -> dict:
    """Per-cell terrain navigability score from gradient Fisher information."""
    step = step or max(terrain.res * 4.0, 100.0)
    R = cfg.radar_noise**2 + cfg.baro_noise**2
    xs = np.arange(0.0, terrain.size + step * 0.5, step)
    ys = np.arange(0.0, terrain.size + step * 0.5, step)
    score = np.zeros((ys.size, xs.size))
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            J = terrain_fisher_information(terrain, float(x), float(y), R)
            w = np.linalg.eigvalsh(J)
            score[j, i] = float(np.sqrt(max(w[-1], 0.0)))
    flat = score.ravel()
    return {
        "xs": xs,
        "ys": ys,
        "score": score,
        "median": float(np.median(flat)),
        "p10": float(np.percentile(flat, 10)),
    }


def _process_matrices(cfg: SimConfig, dt: float) -> tuple[np.ndarray, np.ndarray]:
    F = np.eye(N)
    F[0:2, 2:4] = np.eye(2) * dt
    F[0:2, 4:6] = -0.5 * dt * dt * np.eye(2)
    F[2:4, 4:6] = -dt * np.eye(2)

    q_a = cfg.accel_noise**2
    q_b = cfg.accel_bias_rw**2
    Q = np.zeros((N, N))
    for i in range(2):
        Q[i, i] = q_a * dt**3 / 3.0
        Q[i, i + 2] = Q[i + 2, i] = q_a * dt**2 / 2.0
        Q[i + 2, i + 2] = q_a * dt
        Q[i + 4, i + 4] = q_b * dt
    return F, Q


def _init_information(cfg: SimConfig) -> np.ndarray:
    var = np.array(
        [
            cfg.init_pos_std**2,
            cfg.init_pos_std**2,
            cfg.init_vel_std**2,
            cfg.init_vel_std**2,
            cfg.accel_bias0**2,
            cfg.accel_bias0**2,
        ]
    )
    return np.diag(1.0 / np.maximum(var, 1e-12))


def posterior_crb(
    cfg: SimConfig, terrain: Terrain, truth: Trajectory, R: float | None = None
) -> np.ndarray:
    """Recursive position PCRB RMS lower bound [m] at each truth time step."""
    R = R if R is not None else cfg.radar_noise**2 + cfg.baro_noise**2
    dt = cfg.dt
    F, Q = _process_matrices(cfg, dt)
    J = _init_information(cfg)
    bounds = np.empty(len(truth))
    last_trn = -1e9

    for k, t in enumerate(truth.t):
        try:
            J = np.linalg.inv(Q + F @ np.linalg.inv(J) @ F.T)
        except np.linalg.LinAlgError:
            J = np.linalg.pinv(Q + F @ np.linalg.pinv(J) @ F.T)

        if cfg.trn_update and (t - last_trn) >= cfg.trn_period:
            px, py = truth.pos[k]
            g = terrain.gradient(float(px), float(py))
            H = np.array([g[0], g[1], 0.0, 0.0, 0.0, 0.0])
            J = J + np.outer(H, H) / R
            last_trn = t

        try:
            P = np.linalg.inv(J)
        except np.linalg.LinAlgError:
            P = np.linalg.pinv(J)
        bounds[k] = float(np.sqrt(max(np.trace(P[0:2, 0:2]), 0.0)))

    return bounds


def filter_efficiency(pos_err_rms: float, crb_rms: float) -> float:
    """Statistical efficiency in (0, 1]; 1.0 = meets the PCRB."""
    if pos_err_rms <= 0.0:
        return 0.0
    return float(np.clip(crb_rms / pos_err_rms, 0.0, 1.0))


def efficiency_report(
    res: SimResult, cfg: SimConfig | None = None, terrain: Terrain | None = None
) -> dict:
    """Second-half steady-state efficiency vs PCRB for available filters."""
    cfg = cfg or res.cfg
    terrain = terrain or res.terrain
    crb = posterior_crb(cfg, terrain, res.truth)
    h = len(crb) // 2
    crb_rms = float(np.sqrt(np.mean(crb[h:] ** 2)))

    out: dict = {"crb_rms_m": crb_rms, "crb": crb}
    filters = (
        ("ekf", res.ekf_err),
        ("pf", res.pf_err),
        ("pmf", res.pmf_err),
        ("ins", res.ins_err),
    )
    for name, err in filters:
        if err is None:
            continue
        err_rms = float(np.sqrt(np.mean(err[h:] ** 2)))
        out[f"{name}_rms_m"] = err_rms
        out[f"{name}_efficiency"] = filter_efficiency(err_rms, crb_rms)
    return out
