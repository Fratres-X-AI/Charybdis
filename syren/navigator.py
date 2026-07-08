"""Syren navigator: fuses INS dead-reckoning with TERCOM/TRN via the EKF.

Owns the full GPS-denied navigation loop. Also runs an unaided strapdown INS
in parallel as a drift baseline for comparison.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np

from .config import SimConfig
from .terrain import Terrain
from .imu import ImuSample
from .ins import StrapdownINS
from .tercom import Tercom, TercomFix
from .ekf import NavEKF


@dataclass
class NavRecord:
    ekf_pos: list = field(default_factory=list)
    ekf_std: list = field(default_factory=list)
    ins_pos: list = field(default_factory=list)
    tercom_fix: list = field(default_factory=list)   # (t, pos, cost)
    trn_nis: list = field(default_factory=list)


class Navigator:
    def __init__(self, cfg: SimConfig, terrain: Terrain, pos0, vel0):
        self.cfg = cfg
        self.terrain = terrain
        self.ekf = NavEKF(cfg, terrain, pos0, vel0)
        self.ins = StrapdownINS(pos0, vel0)
        self.tercom = Tercom(cfg, terrain)
        self.rec = NavRecord()
        self._last_trn = -1e9
        self._last_tercom = -1e9

    def step(self, s: ImuSample, t: float) -> None:
        cfg = self.cfg
        # Prediction (dead reckoning inside the EKF) + baseline INS.
        self.ekf.predict(s.accel, cfg.dt)
        self.ins.propagate(s.accel, cfg.dt)

        # Feed TERCOM the current best position estimate + terrain reading.
        self.tercom.push(self.ekf.pos, s.ground_elev)

        # Recursive terrain-referenced update.
        if cfg.trn_update and (t - self._last_trn) >= cfg.trn_period:
            info = self.ekf.update_trn(s.ground_elev)
            self.rec.trn_nis.append((t, info.nis, info.accepted))
            self._last_trn = t

        # Periodic TERCOM correlation fix.
        if (t - self._last_tercom) >= cfg.tercom_period and self.tercom.ready():
            fix: TercomFix | None = self.tercom.correlate()
            if fix is not None and fix.valid:
                self.ekf.update_position(fix.pos, fix.cov)
                self.rec.tercom_fix.append((t, fix.pos.copy(), fix.cost))
            self._last_tercom = t

        self.rec.ekf_pos.append(self.ekf.pos)
        self.rec.ekf_std.append(self.ekf.pos_std)
        self.rec.ins_pos.append(self.ins.pos.copy())

    def arrays(self) -> dict:
        return {
            "ekf_pos": np.array(self.rec.ekf_pos),
            "ekf_std": np.array(self.rec.ekf_std),
            "ins_pos": np.array(self.rec.ins_pos),
        }
