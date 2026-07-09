"""Run the Charybdis GPS-denied navigation simulation and render diagnostics.

Usage:
    python run_sim.py [--duration S] [--seed N]
    python run_sim.py --montecarlo 15         # CEP / NEES evaluation
"""

from __future__ import annotations

import argparse
import os

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from charybdis.config import SimConfig
from charybdis.evaluation import run_montecarlo
from charybdis.simulation import run_simulation

OUT = os.path.join(os.path.dirname(__file__), "outputs")


def plot_map(res, path: str) -> None:
    fig, ax = plt.subplots(figsize=(9, 8))
    ext = [0, res.terrain.size, 0, res.terrain.size]
    im = ax.imshow(
        res.terrain.grid, origin="lower", extent=ext, cmap="terrain", alpha=0.9
    )
    fig.colorbar(im, ax=ax, label="Elevation [m]", shrink=0.8)
    ax.plot(res.truth.pos[:, 0], res.truth.pos[:, 1], "k-", lw=2.0, label="Truth")
    ax.plot(
        res.ins_pos[:, 0], res.ins_pos[:, 1], "r--", lw=1.3, label="INS only (drift)"
    )
    ax.plot(
        res.ekf_pos[:, 0],
        res.ekf_pos[:, 1],
        "c-",
        lw=1.3,
        label="Charybdis EKF (fused)",
    )
    if res.pf_pos is not None:
        ax.plot(
            res.pf_pos[:, 0],
            res.pf_pos[:, 1],
            color="magenta",
            lw=1.3,
            label="Particle filter",
        )
    if res.tercom_fix:
        fx = np.array([f[1] for f in res.tercom_fix])
        ax.scatter(
            fx[:, 0],
            fx[:, 1],
            s=28,
            c="yellow",
            edgecolors="k",
            zorder=5,
            label="TERCOM fix",
        )
    ax.plot(*res.truth.pos[0], "go", ms=9, label="Launch")
    ax.set_xlabel("East [m]")
    ax.set_ylabel("North [m]")
    ax.set_title("Charybdis GDI - Terrain-Aided Navigation")
    ax.legend(loc="upper left", fontsize=8)
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_error(res, path: str) -> None:
    fig, ax = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    ax[0].plot(res.t, res.ins_err, "r-", label="INS only")
    ax[0].plot(res.t, res.ekf_err, "c-", label="Charybdis EKF")
    if res.pf_err is not None:
        ax[0].plot(res.t, res.pf_err, color="magenta", label="Particle filter")
    sig = np.linalg.norm(res.ekf_std, axis=1)
    ax[0].plot(res.t, 3 * sig, "b:", lw=1, label="EKF 3-sigma")
    ax[0].set_ylabel("Horizontal error [m]")
    ax[0].set_yscale("log")
    ax[0].legend(fontsize=8)
    ax[0].grid(alpha=0.3)
    ax[0].set_title("Position error")

    ax[1].plot(res.t, res.ekf_err, "c-", label="Charybdis EKF")
    if res.pf_err is not None:
        ax[1].plot(res.t, res.pf_err, color="magenta", lw=1, label="Particle filter")
    for f in res.tercom_fix:
        ax[1].axvline(f[0], color="orange", alpha=0.25)
    ax[1].set_ylabel("Aided error [m]")
    ax[1].set_xlabel("Time [s]")
    ax[1].grid(alpha=0.3)
    ax[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument(
        "--montecarlo",
        type=int,
        default=0,
        help="run N-seed Monte-Carlo evaluation instead of a single flight",
    )
    args = ap.parse_args()

    cfg = SimConfig()
    if args.duration:
        cfg.duration = args.duration
    if args.seed is not None:
        cfg.seed = args.seed

    if args.montecarlo:
        mc = run_montecarlo(cfg, n_runs=args.montecarlo)
        print("=== Charybdis GDI Monte-Carlo evaluation ===")
        print(mc.table())
        return

    res = run_simulation(cfg)
    os.makedirs(OUT, exist_ok=True)
    plot_map(res, os.path.join(OUT, "map.png"))
    plot_error(res, os.path.join(OUT, "error.png"))

    s = res.summary()
    print("=== Charybdis GDI simulation ===")
    print(f" flight time      : {cfg.duration:.0f} s @ {1 / cfg.dt:.0f} Hz")
    print(f" TERCOM fixes     : {s['n_tercom_fixes']}")
    print(
        f" INS-only  RMSE   : {s['ins_rmse_m']:8.1f} m   final {s['ins_final_m']:8.1f} m"
    )
    print(
        f" Charybdis EKF RMSE: {s['ekf_rmse_m']:8.1f} m   final {s['ekf_final_m']:8.1f} m"
    )
    if "pf_rmse_m" in s:
        print(
            f" Particle  RMSE   : {s['pf_rmse_m']:8.1f} m   final {s['pf_final_m']:8.1f} m"
        )
    print(
        f" drift reduction  : {s['ins_final_m'] / max(s['ekf_final_m'], 1e-6):8.1f} x"
    )
    print(f" plots            : {OUT}")


if __name__ == "__main__":
    main()
