"""Charybdis navigator: fuses INS dead-reckoning with TERCOM/TRN via the EKF.

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
from .pf import TerrainParticleFilter
from .pmf import TerrainPointMassFilter


@dataclass(frozen=True)
class NavEstimate:
    """Stable snapshot for autonomy / UI consumers (do not poke filter internals)."""
    pos: np.ndarray                 # (2,) metres ENU
    cov: np.ndarray                 # (2, 2) position covariance
    source: str                     # "ekf" | "pf" | "pmf" | "ins"
    t: float | None = None
    neff: float | None = None       # particle effective sample size when source=pf
    vel: np.ndarray | None = None

    @property
    def pos_std(self) -> np.ndarray:
        return np.sqrt(np.clip(np.diag(self.cov), 0.0, None))

    @property
    def error_radius_1sigma(self) -> float:
        """Approximate 1σ horizontal error radius from covariance eigenvalues."""
        w = np.linalg.eigvalsh(0.5 * (self.cov + self.cov.T))
        return float(np.sqrt(max(w.max(), 0.0)))


@dataclass
class NavRecord:
    ekf_pos: list = field(default_factory=list)
    ekf_std: list = field(default_factory=list)
    ekf_pcov: list = field(default_factory=list)     # 2x2 position covariance
    ins_pos: list = field(default_factory=list)
    pf_pos: list = field(default_factory=list)
    pf_std: list = field(default_factory=list)
    pf_pcov: list = field(default_factory=list)      # 2x2 particle position covariance
    pmf_pos: list = field(default_factory=list)
    pmf_std: list = field(default_factory=list)
    pmf_pcov: list = field(default_factory=list)     # 2x2 position covariance
    tercom_fix: list = field(default_factory=list)   # (t, pos, cost)
    trn_nis: list = field(default_factory=list)


class Navigator:
    def __init__(self, cfg: SimConfig, terrain: Terrain, pos0, vel0,
                 rng: np.random.Generator | None = None):
        self.cfg = cfg
        self.terrain = terrain
        self.ekf = NavEKF(cfg, terrain, pos0, vel0)
        self.ins = StrapdownINS(pos0, vel0)
        self.tercom = Tercom(cfg, terrain)
        self.pf = TerrainParticleFilter(cfg, terrain, pos0, vel0, rng) \
            if cfg.use_pf else None
        self.pmf = TerrainPointMassFilter(cfg, terrain, pos0, vel0) \
            if cfg.use_pmf else None
        self.rec = NavRecord()
        self._last_trn = -1e9
        self._last_tercom = -1e9

    def step(self, s: ImuSample, t: float) -> None:
        cfg = self.cfg
        # Prediction (dead reckoning inside the EKF) + baseline INS + PF.
        self.ekf.predict(s.accel, cfg.dt)
        self.ins.propagate(s.accel, cfg.dt)
        if self.pf is not None:
            self.pf.predict(s.accel, cfg.dt)
        if self.pmf is not None:
            self.pmf.predict(s.accel, cfg.dt)

        # Feed TERCOM the current best position estimate + terrain reading.
        self.tercom.push(self.ekf.pos, s.ground_elev)

        # Recursive terrain-referenced update.
        if cfg.trn_update and (t - self._last_trn) >= cfg.trn_period:
            info = self.ekf.update_trn(s.ground_elev)
            self.rec.trn_nis.append((t, info.nis, info.accepted))
            if self.pf is not None:
                self.pf.update_trn(s.ground_elev)
            if self.pmf is not None:
                self.pmf.update_trn(s.ground_elev, t)
            self._last_trn = t

        # Periodic TERCOM correlation fix.
        if cfg.use_tercom and (t - self._last_tercom) >= cfg.tercom_period \
                and self.tercom.ready():
            fix: TercomFix | None = self.tercom.correlate()
            if fix is not None and fix.valid:
                self.ekf.update_position(fix.pos, fix.cov)
                if self.pf is not None:
                    self.pf.update_position(fix.pos, fix.cov, t)
                if self.pmf is not None and cfg.pmf_use_tercom:
                    self.pmf.update_position(fix.pos, fix.cov, t)
                self.rec.tercom_fix.append((t, fix.pos.copy(), fix.cost))
            self._last_tercom = t

        self.rec.ekf_pos.append(self.ekf.pos)
        self.rec.ekf_std.append(self.ekf.pos_std)
        self.rec.ekf_pcov.append(self.ekf.P[0:2, 0:2].copy())
        self.rec.ins_pos.append(self.ins.pos.copy())
        if self.pf is not None:
            self.rec.pf_pos.append(self.pf.pos)
            self.rec.pf_std.append(self.pf.pos_std)
            self.rec.pf_pcov.append(self.pf.pos_cov())
        if self.pmf is not None:
            self.rec.pmf_pos.append(self.pmf.pos)
            self.rec.pmf_std.append(self.pmf.pos_std)
            self.rec.pmf_pcov.append(self.pmf.pos_cov())

    def estimate(self, source: str = "auto", t: float | None = None) -> NavEstimate:
        """Return a NavEstimate from the requested filter (default: best available).

        ``source``: ``auto`` prefers PMF → PF → EKF → INS when those filters are enabled.
        """
        if source == "auto":
            if self.pmf is not None:
                source = "pmf"
            elif self.pf is not None:
                source = "pf"
            else:
                source = "ekf"
        if source == "pmf":
            if self.pmf is None:
                raise RuntimeError("PMF disabled (cfg.use_pmf=False)")
            return NavEstimate(
                pos=self.pmf.pos, cov=self.pmf.pos_cov(), source="pmf",
                t=t, vel=self.pmf.vel,
            )
        if source == "pf":
            if self.pf is None:
                raise RuntimeError("PF disabled (cfg.use_pf=False)")
            return NavEstimate(
                pos=self.pf.pos, cov=self.pf.pos_cov(), source="pf",
                t=t, neff=float(self.pf.neff()), vel=self.pf.vel,
            )
        if source == "ekf":
            return NavEstimate(
                pos=self.ekf.pos, cov=self.ekf.P[0:2, 0:2].copy(), source="ekf",
                t=t, vel=self.ekf.vel,
            )
        if source == "ins":
            # Unaided INS has no formal filter covariance; report a large placeholder.
            cov = np.diag([1e6, 1e6])
            return NavEstimate(
                pos=self.ins.pos.copy(), cov=cov, source="ins", t=t,
                vel=self.ins.vel.copy() if hasattr(self.ins, "vel") else None,
            )
        raise ValueError(f"unknown estimate source: {source!r}")

    def arrays(self) -> dict:
        out = {
            "ekf_pos": np.array(self.rec.ekf_pos),
            "ekf_std": np.array(self.rec.ekf_std),
            "ekf_pcov": np.array(self.rec.ekf_pcov),
            "ins_pos": np.array(self.rec.ins_pos),
        }
        if self.pf is not None:
            out["pf_pos"] = np.array(self.rec.pf_pos)
            out["pf_std"] = np.array(self.rec.pf_std)
            out["pf_pcov"] = np.array(self.rec.pf_pcov)
        if self.pmf is not None:
            out["pmf_pos"] = np.array(self.rec.pmf_pos)
            out["pmf_std"] = np.array(self.rec.pmf_std)
            out["pmf_pcov"] = np.array(self.rec.pmf_pcov)
        return out
