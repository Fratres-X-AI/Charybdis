"""Charybdis navigator: fuses INS dead-reckoning, TERCOM/TRN, EKF, and PF.

Owns the full GPS-denied navigation loop. Also runs an unaided strapdown INS
in parallel as a drift baseline for comparison.

Coordination layer (:meth:`_coordinate`)
----------------------------------------
The particle filter watches the EKF and intervenes when it goes wrong:

* **Divergence detection** - a cross-filter Mahalanobis test (does the EKF's
  posterior disagree with the robust reference by more than their combined
  covariance allows?) plus a sustained-high-NIS fault flag from the EKF's own
  innovation monitor.
* **Recovery** - when the EKF is judged diverged *and* the reference is confident
  and unambiguous, the EKF position/velocity are re-seeded from the reference
  (:meth:`NavEKF.reset_from`) with an inflated covariance.
* **Soft help** - when the EKF is merely uncertain (not yet diverged) and the
  reference is tighter, the reference is folded in as an inflated pseudo-position
  measurement (conservative, correlation-aware).
* **Mode management** - PF multi-modality suppresses resets/soft-help (never
  trust an ambiguous reference) and is surfaced on :class:`NavEstimate`.
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
from . import estimation as est


@dataclass(frozen=True)
class NavEstimate:
    """Stable snapshot for autonomy / UI consumers (do not poke filter internals)."""
    pos: np.ndarray                 # (2,) metres ENU
    cov: np.ndarray                 # (2, 2) position covariance
    source: str                     # "ekf" | "pf" | "pmf" | "ins"
    t: float | None = None
    neff: float | None = None       # particle effective sample size when source=pf
    vel: np.ndarray | None = None
    ambiguous: bool = False         # terrain currently multi-hypothesis
    n_modes: int | None = None      # significant position modes (if known)
    ekf_healthy: bool = True        # EKF not currently flagged diverged

    @property
    def pos_std(self) -> np.ndarray:
        return np.sqrt(np.clip(np.diag(self.cov), 0.0, None))

    @property
    def error_radius_1sigma(self) -> float:
        """Approximate 1σ horizontal error radius from covariance eigenvalues."""
        w = np.linalg.eigvalsh(0.5 * (self.cov + self.cov.T))
        return float(np.sqrt(max(w.max(), 0.0)))


@dataclass
class _Reference:
    """PF posterior used to supervise/rescue the EKF."""
    pos: np.ndarray
    cov: np.ndarray
    vel: np.ndarray
    std: float
    n_modes: int
    ambiguous: bool
    confident: bool
    source: str


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
    ekf_reset: list = field(default_factory=list)    # (t, to_pos, from_pos, src)
    fusion_soft: list = field(default_factory=list)  # (t, omega)
    ambiguity: list = field(default_factory=list)    # (t, n_modes, ambiguous)
    ekf_qscale: list = field(default_factory=list)   # (t, q_scale)


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
        self._last_fusion = -1e9
        self._last_reset = -1e9
        self._ambiguous = False
        self._n_modes = 1
        self._ekf_healthy = True

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

        # Coordinate the filters (divergence detection, recovery, modes).
        if (cfg.filter_fusion or cfg.mode_mgmt) \
                and (t - self._last_fusion) >= cfg.fusion_period:
            self._coordinate(t)
            self._last_fusion = t

        self.rec.ekf_pos.append(self.ekf.pos)
        self.rec.ekf_std.append(self.ekf.pos_std)
        self.rec.ekf_pcov.append(self.ekf.P[0:2, 0:2].copy())
        self.rec.ins_pos.append(self.ins.pos.copy())
        self.rec.ekf_qscale.append((t, self.ekf.last_q_scale))
        if self.pf is not None:
            self.rec.pf_pos.append(self.pf.pos)
            self.rec.pf_std.append(self.pf.pos_std)
            self.rec.pf_pcov.append(self.pf.pos_cov())
        if self.pmf is not None:
            self.rec.pmf_pos.append(self.pmf.pos)
            self.rec.pmf_std.append(self.pmf.pos_std)
            self.rec.pmf_pcov.append(self.pmf.pos_cov())

    # ---- coordination layer -------------------------------------------- #
    def _reference(self) -> _Reference | None:
        """Build the PF reference posterior used to supervise the EKF.

        PMF may still run for legacy evaluation, but it is deliberately not used
        for core EKF recovery in the current navigation scope.
        """
        cfg = self.cfg
        if self.pf is None:
            return None
        pos, cov, vel = self.pf.pos, self.pf.pos_cov(), self.pf.vel
        n_modes = self.pf.n_modes()
        ambiguous = n_modes >= 2
        neff_ok = self.pf.neff() >= cfg.ref_confident_neff * self.pf.N
        src = "pf"
        std = float(np.sqrt(max(np.linalg.eigvalsh(0.5 * (cov + cov.T)).max(), 0.0)))
        confident = (std <= cfg.ref_confident_std) and neff_ok and not ambiguous
        return _Reference(pos=np.asarray(pos, float), cov=np.asarray(cov, float),
                          vel=np.asarray(vel, float), std=std, n_modes=int(n_modes),
                          ambiguous=bool(ambiguous), confident=bool(confident),
                          source=src)

    def _coordinate(self, t: float) -> None:
        cfg = self.cfg
        ref = self._reference()
        if ref is None:
            return

        if cfg.mode_mgmt:
            self._ambiguous = ref.ambiguous
            self._n_modes = ref.n_modes
            self.rec.ambiguity.append((t, ref.n_modes, ref.ambiguous))

        if not cfg.filter_fusion:
            return

        ekf_pcov = self.ekf.P[0:2, 0:2]
        delta = self.ekf.pos - ref.pos
        d_maha = est.mahalanobis2(delta, ekf_pcov + ref.cov)
        nis_fault = self.ekf.monitor.faulted(cfg.ekf_div_nis, cfg.adapt_q_min_count)
        diverged = (d_maha > cfg.ekf_div_maha) or nis_fault
        self._ekf_healthy = not diverged

        # never act on an ambiguous / low-confidence reference
        if ref.ambiguous or not ref.confident:
            return

        # --- hard recovery: re-seed a diverged EKF from the robust filter ---
        if diverged and (t - self._last_reset) >= cfg.ekf_reset_cooldown:
            from_pos = self.ekf.pos.copy()
            self.ekf.reset_from(ref.pos, ref.cov, vel=ref.vel,
                                infl=cfg.ekf_reset_infl)
            self.rec.ekf_reset.append((t, self.ekf.pos.copy(), from_pos, ref.source))
            self._last_reset = t
            return

        # --- soft help: fold a tighter reference into an over-uncertain EKF ---
        ekf_std = float(np.sqrt(max(np.linalg.eigvalsh(
            0.5 * (ekf_pcov + ekf_pcov.T)).max(), 0.0)))
        if ekf_std > cfg.fusion_ci_help_std and np.trace(ref.cov) < np.trace(ekf_pcov):
            _, _, omega = est.covariance_intersection(
                self.ekf.pos, ekf_pcov, ref.pos, ref.cov)
            # apply CI conservatively as an inflated pseudo-measurement so the
            # full state (incl. velocity/bias) updates consistently via cross-cov
            R_soft = ref.cov / max(1.0 - omega, 0.15)
            self.ekf.update_position(ref.pos, R_soft)
            self.rec.fusion_soft.append((t, omega))

    def estimate(self, source: str = "auto", t: float | None = None) -> NavEstimate:
        """Return a NavEstimate from the requested filter (default: best available).

        ``source``: ``auto`` preserves the existing PMF → PF → EKF preference
        for callers. EKF recovery itself is PF-only.
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
                t=t, vel=self.pmf.vel, ambiguous=self._ambiguous,
                n_modes=self._n_modes, ekf_healthy=self._ekf_healthy,
            )
        if source == "pf":
            if self.pf is None:
                raise RuntimeError("PF disabled (cfg.use_pf=False)")
            return NavEstimate(
                pos=self.pf.pos, cov=self.pf.pos_cov(), source="pf",
                t=t, neff=float(self.pf.neff()), vel=self.pf.vel,
                ambiguous=self._ambiguous, n_modes=self._n_modes,
                ekf_healthy=self._ekf_healthy,
            )
        if source == "ekf":
            return NavEstimate(
                pos=self.ekf.pos, cov=self.ekf.P[0:2, 0:2].copy(), source="ekf",
                t=t, vel=self.ekf.vel, ambiguous=self._ambiguous,
                n_modes=self._n_modes, ekf_healthy=self._ekf_healthy,
            )
        if source == "ins":
            # Unaided INS has no formal filter covariance; report a large placeholder.
            cov = np.diag([1e6, 1e6])
            return NavEstimate(
                pos=self.ins.pos.copy(), cov=cov, source="ins", t=t,
                vel=self.ins.vel.copy() if hasattr(self.ins, "vel") else None,
            )
        raise ValueError(f"unknown estimate source: {source!r}")

    def action_envelope(
        self,
        *,
        t: float | None = None,
        threat: float = 0.0,
        map_trust: float = 1.0,
    ):
        """Continuous action authority from current nav/evidence state."""
        from .action_envelope import compute_action_envelope

        return compute_action_envelope(
            self, self.terrain, t=t, threat=threat, map_trust=map_trust,
        )

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
