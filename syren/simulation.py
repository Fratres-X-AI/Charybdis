"""End-to-end simulation harness for Syren."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .config import SimConfig
from .terrain import Terrain
from .trajectory import generate_truth, Trajectory
from .imu import IMU
from .navigator import Navigator


@dataclass
class SimResult:
    cfg: SimConfig
    terrain: Terrain
    truth: Trajectory
    t: np.ndarray
    ekf_pos: np.ndarray
    ekf_std: np.ndarray
    ins_pos: np.ndarray
    tercom_fix: list
    ekf_err: np.ndarray
    ins_err: np.ndarray

    def summary(self) -> dict:
        def rmse(e):
            return float(np.sqrt(np.mean(e ** 2)))
        return {
            "ekf_rmse_m": rmse(self.ekf_err),
            "ekf_final_m": float(self.ekf_err[-1]),
            "ekf_max_m": float(self.ekf_err.max()),
            "ins_rmse_m": rmse(self.ins_err),
            "ins_final_m": float(self.ins_err[-1]),
            "ins_max_m": float(self.ins_err.max()),
            "n_tercom_fixes": len(self.tercom_fix),
        }


def run_simulation(cfg: SimConfig | None = None) -> SimResult:
    cfg = cfg or SimConfig()
    terrain = Terrain.synthetic(cfg)
    truth = generate_truth(cfg, terrain)
    imu = IMU(cfg, terrain)

    nav = Navigator(cfg, terrain, pos0=truth.pos[0], vel0=truth.vel[0])
    for k in range(len(truth)):
        sample = imu.sample(truth, k)
        nav.step(sample, truth.t[k])

    a = nav.arrays()
    ekf_err = np.linalg.norm(a["ekf_pos"] - truth.pos, axis=1)
    ins_err = np.linalg.norm(a["ins_pos"] - truth.pos, axis=1)
    return SimResult(
        cfg=cfg,
        terrain=terrain,
        truth=truth,
        t=truth.t,
        ekf_pos=a["ekf_pos"],
        ekf_std=a["ekf_std"],
        ins_pos=a["ins_pos"],
        tercom_fix=nav.rec.tercom_fix,
        ekf_err=ekf_err,
        ins_err=ins_err,
    )
