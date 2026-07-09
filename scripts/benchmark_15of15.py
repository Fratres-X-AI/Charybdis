#!/usr/bin/env python3
"""Print benchmark numbers for the four deferred features."""

from __future__ import annotations

import numpy as np
from console import charybdis_core as core
from console import charybdis_slam as slam
from console import charybdis_swarm as swarm


def bench_slam(ticks: int = 100) -> float:
    p = core.SimParams(autonomy=False, n_contacts=0, drift=18.0)
    s = core.init_state(seed=3, params=p)
    sm = slam.init_slam(core.START)
    dr_errs, slam_errs = [], []
    for _ in range(ticks):
        core.step(s, p)
        v = s.true_path[-1] - s.true_path[-2] if len(s.true_path) > 1 else np.zeros(2)
        slam.slam_step(sm, v, core.bathymetry, dt=core.DT)
        dr_errs.append(float(np.hypot(*(s.true_pos - s.est_pos))))
        slam_errs.append(slam.position_error(sm, s.true_pos))
    return float(np.mean(dr_errs) / max(np.mean(slam_errs), 1e-6))


def bench_swarm() -> dict:
    return swarm.montecarlo_compare(n_runs=6, ticks=60, workers=2)


def bench_nn() -> dict:
    pytest = __import__("pytest")
    pytest.importorskip("torch")
    from pathlib import Path

    from console import charybdis_nn as nn

    tmp = Path("models/tcm_cnn.pt")
    if not tmp.is_file():
        nn.train(model_path=tmp, n_samples=4000, epochs=3, batch=256)
    nn.load_model(tmp, device="cpu")
    true = core.ANOMALIES["RIDGE BRAVO"] + np.array([0.5, -0.5])
    est = true + np.array([3.0, -2.5])
    corr_c, peak_c, _ = core.tcm_cross_correlation(true, est)
    corr_n, peak_n, _ = nn.tcm_nn_match(true, est, core.bathymetry, model_path=tmp)
    return {
        "classical_err_m": float(np.linalg.norm(corr_c - true)),
        "nn_err_m": float(np.linalg.norm(corr_n - true)),
        "classical_peak": peak_c,
        "nn_peak": peak_n,
    }


if __name__ == "__main__":
    print("=== Charybdis 15/15 benchmarks ===")
    print(f"SLAM drift reduction factor: {bench_slam():.2f}x")
    sw = bench_swarm()
    sw = swarm.montecarlo_compare(n_runs=12, ticks=70, workers=31)
    print(
        f"Swarm team CEP50: {sw['team_cep50_m']:.2f} m  solo: {sw['solo_cep50_m']:.2f} m  "
        f"({sw['improvement_x']:.2f}x)"
    )
    try:
        nnm = bench_nn()
        print(
            f"NN TCM err: {nnm['nn_err_m']:.2f} m  classical: {nnm['classical_err_m']:.2f} m"
        )
    except Exception as exc:
        print(f"NN benchmark skipped: {exc}")
    print("ROS2: run scripts/ros2_smoke.sh (Docker, not in CI)")
