"""End-to-end simulation harness for Charybdis."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from ..config import SimConfig
from ..terrain import Terrain
from ..trajectory import generate_truth, Trajectory
from ..imu import IMU
from ..legacy.navigator import Navigator


@dataclass
class SimResult:
    cfg: SimConfig
    terrain: Terrain
    truth: Trajectory
    t: np.ndarray
    ekf_pos: np.ndarray
    ekf_std: np.ndarray
    ekf_pcov: np.ndarray
    ins_pos: np.ndarray
    tercom_fix: list
    ekf_err: np.ndarray
    ins_err: np.ndarray
    pf_pos: np.ndarray | None = None
    pf_std: np.ndarray | None = None
    pf_pcov: np.ndarray | None = None
    pf_err: np.ndarray | None = None
    pmf_pos: np.ndarray | None = None
    pmf_std: np.ndarray | None = None
    pmf_pcov: np.ndarray | None = None
    pmf_err: np.ndarray | None = None
    n_ekf_resets: int = 0            # PF-driven EKF recoveries
    n_ambiguous: int = 0            # ambiguity-flagged coordination checks
    n_coord_checks: int = 0         # total coordination checks

    def summary(self) -> dict:
        def rmse(e):
            return float(np.sqrt(np.mean(e ** 2)))
        out = {
            "ekf_rmse_m": rmse(self.ekf_err),
            "ekf_final_m": float(self.ekf_err[-1]),
            "ekf_max_m": float(self.ekf_err.max()),
            "ins_rmse_m": rmse(self.ins_err),
            "ins_final_m": float(self.ins_err[-1]),
            "ins_max_m": float(self.ins_err.max()),
            "n_tercom_fixes": len(self.tercom_fix),
        }
        if self.pf_err is not None:
            out["pf_rmse_m"] = rmse(self.pf_err)
            out["pf_final_m"] = float(self.pf_err[-1])
            out["pf_max_m"] = float(self.pf_err.max())
        if self.pmf_err is not None:
            out["pmf_rmse_m"] = rmse(self.pmf_err)
            out["pmf_final_m"] = float(self.pmf_err[-1])
            out["pmf_max_m"] = float(self.pmf_err.max())
        return out


def run_simulation(cfg: SimConfig | None = None,
                   terrain: Terrain | None = None) -> SimResult:
    cfg = cfg or SimConfig()
    terrain = terrain or Terrain.synthetic(cfg)
    truth = generate_truth(cfg, terrain)
    imu = IMU(cfg, terrain)

    pf_rng = np.random.default_rng(cfg.seed + 202)
    pos0 = np.array(truth.pos[0], float)
    if cfg.init_pos_error > 0:
        off_rng = np.random.default_rng(cfg.seed + 303)
        theta = off_rng.uniform(0.0, 2 * np.pi)
        pos0 = pos0 + cfg.init_pos_error * np.array([np.cos(theta), np.sin(theta)])
    nav = Navigator(cfg, terrain, pos0=pos0, vel0=truth.vel[0], rng=pf_rng)
    for k in range(len(truth)):
        sample = imu.sample(truth, k)
        nav.step(sample, truth.t[k])

    a = nav.arrays()
    ekf_err = np.linalg.norm(a["ekf_pos"] - truth.pos, axis=1)
    ins_err = np.linalg.norm(a["ins_pos"] - truth.pos, axis=1)
    pf_pos = a.get("pf_pos")
    pf_std = a.get("pf_std")
    pf_pcov = a.get("pf_pcov")
    pf_err = None if pf_pos is None else np.linalg.norm(pf_pos - truth.pos, axis=1)
    pmf_pos = a.get("pmf_pos")
    pmf_std = a.get("pmf_std")
    pmf_pcov = a.get("pmf_pcov")
    pmf_err = None if pmf_pos is None else np.linalg.norm(pmf_pos - truth.pos, axis=1)
    return SimResult(
        cfg=cfg,
        terrain=terrain,
        truth=truth,
        t=truth.t,
        ekf_pos=a["ekf_pos"],
        ekf_std=a["ekf_std"],
        ekf_pcov=a["ekf_pcov"],
        ins_pos=a["ins_pos"],
        tercom_fix=nav.rec.tercom_fix,
        ekf_err=ekf_err,
        ins_err=ins_err,
        pf_pos=pf_pos,
        pf_std=pf_std,
        pf_pcov=pf_pcov,
        pf_err=pf_err,
        pmf_pos=pmf_pos,
        pmf_std=pmf_std,
        pmf_pcov=pmf_pcov,
        pmf_err=pmf_err,
        n_ekf_resets=len(nav.rec.ekf_reset),
        n_ambiguous=int(sum(1 for _, _, amb in nav.rec.ambiguity if amb)),
        n_coord_checks=len(nav.rec.ambiguity),
    )
