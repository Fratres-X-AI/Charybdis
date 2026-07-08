"""Monte-Carlo evaluation of the Charybdis navigation filters.

Runs the full simulation across many random seeds and reports the metrics a
GNC engineer actually signs off on:

  * CEP50 / CEP95  - circular error probable (median / 95th pct final error).
  * RMSE           - mean root-mean-square horizontal error over the flight.
  * EKF NEES       - normalised estimation error squared, the filter-consistency
                     check. For a 2-DOF position state a consistent filter gives
                     an average NEES near 2.0; much larger means the filter is
                     over-confident (covariance too small).
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import numpy as np

from .config import SimConfig
from .simulation import run_simulation

FILTERS = ("ins", "ekf", "pf", "pmf")


@dataclass
class MonteCarloResult:
    n_runs: int
    seeds: list
    final_err: dict          # filter -> np.ndarray of final errors [m]
    rmse: dict               # filter -> np.ndarray of per-run RMSE [m]
    ekf_nees: float
    pmf_nees: float = 0.0

    def cep(self, filt: str, q: float = 50.0) -> float:
        return float(np.percentile(self.final_err[filt], q))

    def mean_rmse(self, filt: str) -> float:
        return float(np.mean(self.rmse[filt]))

    def table(self) -> str:
        rows = [f"Monte-Carlo over {self.n_runs} runs",
                f"{'filter':<6}{'CEP50 [m]':>12}{'CEP95 [m]':>12}{'RMSE [m]':>12}"]
        for f in FILTERS:
            if f not in self.final_err:
                continue
            rows.append(f"{f.upper():<6}{self.cep(f,50):>12.1f}"
                        f"{self.cep(f,95):>12.1f}{self.mean_rmse(f):>12.1f}")
        rows.append(f"EKF NEES (2-DOF, ~2.0 ideal): {self.ekf_nees:.2f}")
        if "pmf" in self.final_err:
            rows.append(f"PMF NEES (2-DOF, ~2.0 ideal): {self.pmf_nees:.2f}")
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
    nees_all = []
    pmf_nees_all = []

    for seed in seeds:
        cfg = replace(base_cfg, seed=int(seed))
        if duration is not None:
            cfg = replace(cfg, duration=duration)
        res = run_simulation(cfg)

        final["ins"].append(res.ins_err[-1])
        final["ekf"].append(res.ekf_err[-1])
        rmse["ins"].append(np.sqrt(np.mean(res.ins_err ** 2)))
        rmse["ekf"].append(np.sqrt(np.mean(res.ekf_err ** 2)))
        if res.pf_err is not None:
            final["pf"].append(res.pf_err[-1])
            rmse["pf"].append(np.sqrt(np.mean(res.pf_err ** 2)))
        if res.pmf_err is not None:
            final["pmf"].append(res.pmf_err[-1])
            rmse["pmf"].append(np.sqrt(np.mean(res.pmf_err ** 2)))
            pmf_nees_all.append(
                _nees_second_half(res.pmf_pos, res.pmf_pcov, res.truth.pos))
        nees_all.append(_nees_second_half(res.ekf_pos, res.ekf_pcov, res.truth.pos))

    final = {f: np.array(v) for f, v in final.items() if v}
    rmse = {f: np.array(v) for f, v in rmse.items() if v}
    ekf_nees = float(np.mean(np.concatenate(nees_all)))
    pmf_nees = float(np.mean(np.concatenate(pmf_nees_all))) if pmf_nees_all else 0.0
    return MonteCarloResult(n_runs=n_runs, seeds=list(seeds), final_err=final,
                            rmse=rmse, ekf_nees=ekf_nees, pmf_nees=pmf_nees)
