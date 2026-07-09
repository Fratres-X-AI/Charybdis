"""Parallel PMF validation sweep (pod, many cores).

Runs nominal + TRN-only over many seeds and a large-initial-error scenario,
reporting per-filter CEP50/CEP95, mean final error, divergence count, and NEES.
Usage: OMP_NUM_THREADS=1 python scripts/pmf_sweep.py [n_seeds]
"""

from __future__ import annotations

import os
import sys

import numpy as np

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

from dataclasses import replace
from multiprocessing import Pool

from charybdis.config import SimConfig
from charybdis.parallel import pool_workers
from charybdis.simulation import run_simulation


def _nees_pos(pos, pcov, truth):
    """Mean 2-dof position NEES over the second half of the run."""
    if pos is None or pcov is None:
        return float("nan")
    h = len(pos) // 2
    acc = []
    for k in range(h, len(pos)):
        e = pos[k] - truth[k]
        P = pcov[k] + 1e-6 * np.eye(2)
        acc.append(float(e @ np.linalg.inv(P) @ e))
    return float(np.mean(acc)) if acc else float("nan")


def one(args):
    seed, mode = args
    base = SimConfig(duration=100.0)
    if mode == "nominal":
        cfg = replace(base, seed=seed, use_tercom=True)
    elif mode == "trn":
        cfg = replace(base, seed=seed, use_tercom=False)
    elif mode == "large":
        cfg = replace(
            base, seed=seed, use_tercom=False, init_pos_error=450.0, init_pos_std=500.0
        )
    r = run_simulation(cfg)
    s = r.summary()
    truth = r.truth.pos
    out = {
        "seed": seed,
        "mode": mode,
        "pmf": s["pmf_final_m"],
        "ekf": s["ekf_final_m"],
        "pf": s["pf_final_m"],
        "pmf_rmse": s["pmf_rmse_m"],
        "ekf_rmse": s["ekf_rmse_m"],
        "pmf_nees": _nees_pos(r.pmf_pos, r.pmf_pcov, truth),
        "ekf_nees": _nees_pos(r.ekf_pos, r.ekf_pcov, truth),
    }
    return out


def summarize(rows, mode):
    rows = [r for r in rows if r["mode"] == mode]

    def stat(key):
        v = np.array([r[key] for r in rows], float)
        v = v[np.isfinite(v)]
        return v

    for f in ("pmf", "ekf", "pf"):
        v = stat(f)
        cep50 = np.percentile(v, 50)
        cep95 = np.percentile(v, 95)
        div = int(np.sum(v > 150.0))
        line = f"  {f.upper():4s} CEP50={cep50:6.1f} CEP95={cep95:6.1f} mean={v.mean():6.1f} div>150m={div}/{len(v)}"
        if f in ("pmf", "ekf"):
            nv = stat(f + "_nees")
            line += f"  NEES={nv.mean():5.2f}"
        print(line)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 64
    seeds = list(range(1, n + 1))
    jobs = [(s, m) for m in ("nominal", "trn", "large") for s in seeds]
    with Pool(processes=pool_workers(31)) as pool:
        rows = pool.map(one, jobs)
    for mode in ("nominal", "trn", "large"):
        print(f"[{mode}]  ({n} seeds)")
        summarize(rows, mode)


if __name__ == "__main__":
    main()
