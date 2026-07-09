"""Monte-Carlo evaluation of the Charybdis navigation filters.

Runs the full simulation across many random seeds and reports the metrics a
GNC engineer actually signs off on:

  * CEP50 / CEP95  - circular error probable (median / 95th pct final error).
  * RMSE           - mean root-mean-square horizontal error over the flight.
  * NEES           - normalised estimation error squared, the filter-consistency
                     check. For a 2-DOF position state a consistent filter gives
                     an average NEES near 2.0 (ANEES near 1.0); much larger means
                     the filter is over-confident (covariance too small), much
                     smaller means it is conservative.
  * NEES coverage  - fraction of samples inside the 2-DOF 95% band; a consistent
                     filter covers ~0.95. This catches heavy-tailed error
                     distributions that a mean-NEES check alone would miss.
  * Divergence     - fraction of runs whose final error exceeds a hard threshold.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import numpy as np

from .config import SimConfig
from .simulation import run_simulation

FILTERS = ("ins", "ekf", "pf", "pmf")

# Two-sided 95% interval of a chi-square with 2 DOF (position consistency band).
CHI2_2DOF_LO = 0.05064
CHI2_2DOF_HI = 7.37776


@dataclass
class MonteCarloResult:
    n_runs: int
    seeds: list
    final_err: dict          # filter -> np.ndarray of final errors [m]
    rmse: dict               # filter -> np.ndarray of per-run RMSE [m]
    ekf_nees: float
    pmf_nees: float = 0.0
    pf_nees: float = 0.0
    nees_samples: dict = field(default_factory=dict)   # filter -> NEES samples
    n_resets: float = 0.0    # mean EKF recoveries per run
    n_ambiguous: float = 0.0  # mean ambiguity-flagged checks per run

    # ---- point metrics -------------------------------------------------- #
    def cep(self, filt: str, q: float = 50.0) -> float:
        return float(np.percentile(self.final_err[filt], q))

    def mean_rmse(self, filt: str) -> float:
        return float(np.mean(self.rmse[filt]))

    def divergence_rate(self, filt: str, thresh: float = 150.0) -> float:
        if filt not in self.final_err:
            return 0.0
        return float(np.mean(self.final_err[filt] > thresh))

    # ---- consistency ---------------------------------------------------- #
    def anees(self, filt: str) -> float:
        """Average NEES / DOF (2-DOF position); 1.0 == perfectly consistent."""
        s = self.nees_samples.get(filt)
        if s is None or len(s) == 0:
            return 0.0
        return float(np.mean(s) / 2.0)

    def nees_coverage(self, filt: str) -> float:
        """Fraction of NEES samples inside the 2-DOF 95% band (~0.95 ideal)."""
        s = self.nees_samples.get(filt)
        if s is None or len(s) == 0:
            return 0.0
        return float(np.mean((s >= CHI2_2DOF_LO) & (s <= CHI2_2DOF_HI)))

    def table(self) -> str:
        rows = [f"Monte-Carlo over {self.n_runs} runs",
                f"{'filter':<6}{'CEP50 [m]':>11}{'CEP95 [m]':>11}"
                f"{'RMSE [m]':>11}{'ANEES':>8}{'cover':>8}{'div%':>7}"]
        for f in FILTERS:
            if f not in self.final_err:
                continue
            rows.append(
                f"{f.upper():<6}{self.cep(f,50):>11.1f}{self.cep(f,95):>11.1f}"
                f"{self.mean_rmse(f):>11.1f}{self.anees(f):>8.2f}"
                f"{self.nees_coverage(f):>8.2f}{100*self.divergence_rate(f):>7.1f}")
        rows.append(f"EKF NEES (2-DOF, ~2.0 ideal): {self.ekf_nees:.2f}")
        if "pmf" in self.final_err:
            rows.append(f"PMF NEES (2-DOF, ~2.0 ideal): {self.pmf_nees:.2f}")
        if self.n_resets:
            rows.append(f"EKF recoveries/run: {self.n_resets:.2f}   "
                        f"ambiguity checks/run: {self.n_ambiguous:.2f}")
        return "\n".join(rows)


def _nees_second_half(pos: np.ndarray, pcov: np.ndarray,
                      truth_pos: np.ndarray) -> np.ndarray:
    e = pos - truth_pos
    t0 = len(e) // 2
    out = np.empty(len(e) - t0)
    for i, k in enumerate(range(t0, len(e))):
        try:
            Pinv = np.linalg.inv(pcov[k])
        except np.linalg.LinAlgError:
            Pinv = np.linalg.pinv(pcov[k])
        out[i] = float(e[k] @ Pinv @ e[k])
    return out


def run_montecarlo(base_cfg: SimConfig | None = None, n_runs: int = 15,
                   seeds=None, duration: float | None = None) -> MonteCarloResult:
    base_cfg = base_cfg or SimConfig()
    if seeds is None:
        seeds = list(range(1, n_runs + 1))
    n_runs = len(seeds)

    final = {f: [] for f in FILTERS}
    rmse = {f: [] for f in FILTERS}
    nees_all = {"ekf": [], "pf": [], "pmf": []}
    n_resets: list[int] = []
    n_ambiguous: list[int] = []

    for seed in seeds:
        cfg = replace(base_cfg, seed=int(seed))
        if duration is not None:
            cfg = replace(cfg, duration=duration)
        res = run_simulation(cfg)

        final["ins"].append(res.ins_err[-1])
        final["ekf"].append(res.ekf_err[-1])
        rmse["ins"].append(np.sqrt(np.mean(res.ins_err ** 2)))
        rmse["ekf"].append(np.sqrt(np.mean(res.ekf_err ** 2)))
        nees_all["ekf"].append(
            _nees_second_half(res.ekf_pos, res.ekf_pcov, res.truth.pos))
        if res.pf_err is not None:
            final["pf"].append(res.pf_err[-1])
            rmse["pf"].append(np.sqrt(np.mean(res.pf_err ** 2)))
            if res.pf_pcov is not None:
                nees_all["pf"].append(
                    _nees_second_half(res.pf_pos, res.pf_pcov, res.truth.pos))
        if res.pmf_err is not None:
            final["pmf"].append(res.pmf_err[-1])
            rmse["pmf"].append(np.sqrt(np.mean(res.pmf_err ** 2)))
            nees_all["pmf"].append(
                _nees_second_half(res.pmf_pos, res.pmf_pcov, res.truth.pos))
        n_resets.append(res.n_ekf_resets)
        n_ambiguous.append(res.n_ambiguous)

    final = {f: np.array(v) for f, v in final.items() if v}
    rmse = {f: np.array(v) for f, v in rmse.items() if v}
    nees_samples = {f: np.concatenate(v) for f, v in nees_all.items() if v}
    ekf_nees = float(np.mean(nees_samples["ekf"]))
    pmf_nees = float(np.mean(nees_samples["pmf"])) if "pmf" in nees_samples else 0.0
    pf_nees = float(np.mean(nees_samples["pf"])) if "pf" in nees_samples else 0.0
    return MonteCarloResult(
        n_runs=n_runs, seeds=list(seeds), final_err=final, rmse=rmse,
        ekf_nees=ekf_nees, pmf_nees=pmf_nees, pf_nees=pf_nees,
        nees_samples=nees_samples,
        n_resets=float(np.mean(n_resets)) if n_resets else 0.0,
        n_ambiguous=float(np.mean(n_ambiguous)) if n_ambiguous else 0.0)
