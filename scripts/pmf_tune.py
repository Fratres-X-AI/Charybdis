"""Tune pmf_meas_infl for NEES consistency (target ~2.0) vs robustness.
Usage: OMP_NUM_THREADS=1 python scripts/pmf_tune.py [n_seeds]
"""
from __future__ import annotations

import os
import sys

import numpy as np

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

from multiprocessing import Pool

from charybdis import SimConfig, run_simulation
from charybdis.parallel import pool_workers

INFLS = [0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 6.0]


def _nees(pos, pcov, truth):
    h = len(pos) // 2
    acc = []
    for k in range(h, len(pos)):
        e = pos[k] - truth[k]
        acc.append(float(e @ np.linalg.inv(pcov[k] + 1e-6 * np.eye(2)) @ e))
    return float(np.mean(acc))


def one(args):
    seed, infl, mode = args
    kw = dict(seed=seed, duration=100.0, pmf_meas_infl=infl, use_tercom=False,
              use_pf=False)
    if mode == "large":
        kw.update(init_pos_error=450.0, init_pos_std=500.0)
    r = run_simulation(SimConfig(**kw))
    s = r.summary()
    return (infl, mode, s["pmf_final_m"], _nees(r.pmf_pos, r.pmf_pcov, r.truth.pos))


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 48
    jobs = [(seed, infl, mode)
            for mode in ("trn", "large")
            for infl in INFLS
            for seed in range(1, n + 1)]
    with Pool(processes=pool_workers(31)) as pool:
        rows = pool.map(one, jobs)
    for mode in ("trn", "large"):
        print(f"[{mode}] ({n} seeds)")
        for infl in INFLS:
            fin = np.array([r[2] for r in rows if r[0] == infl and r[1] == mode])
            nees = np.array([r[3] for r in rows if r[0] == infl and r[1] == mode])
            nees = nees[np.isfinite(nees)]
            print(f"  infl={infl:4.2f} CEP50={np.percentile(fin,50):6.1f} "
                  f"CEP95={np.percentile(fin,95):6.1f} mean={fin.mean():6.1f} "
                  f"div>150={int((fin>150).sum()):2d}/{len(fin)} NEES={nees.mean():5.2f}")


if __name__ == "__main__":
    main()
