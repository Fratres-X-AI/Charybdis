#!/usr/bin/env python3
"""Real-region (or synthetic-fallback) Monte-Carlo for the GDI stack.

Usage:
  python scripts/mc_real_region.py                  # synthetic DEM fallback
  python scripts/mc_real_region.py --npz path.npz  # GEBCO/exported tile
  python scripts/mc_real_region.py --n-runs 8 --duration 60

No GPU / RunPod required. Keep n_runs small on laptops; use pod for large MC.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from charybdis.bathy import load_npz, terrain_suitability
from charybdis.config import SimConfig
from charybdis.evaluation import run_montecarlo
from charybdis.imu import IMU
from charybdis.legacy.navigator import Navigator
from charybdis.terrain import Terrain
from charybdis.trajectory import generate_truth


def _load_terrain(npz: str | None, seed: int) -> Terrain:
    if npz:
        terr = load_npz(npz)
        print(f"loaded terrain {npz} shape={terr.grid.shape} res={terr.res:.1f}m")
        return terr
    cfg = SimConfig(seed=seed)
    terr = Terrain.synthetic(cfg)
    print(f"synthetic terrain fallback seed={seed} size={terr.size:.0f}m")
    return terr


def _run_on_terrain(
    cfg: SimConfig, terrain: Terrain, n_runs: int
) -> dict[str, list[float]]:
    finals: dict[str, list[float]] = {"ekf": [], "ins": [], "pf": [], "pmf": []}
    for i in range(n_runs):
        c = replace(cfg, seed=cfg.seed + i)
        truth = generate_truth(c, terrain)
        nav = Navigator(c, terrain, truth.pos[0], truth.vel[0])
        imu = IMU(c, terrain)
        for k in range(1, len(truth)):
            nav.step(imu.sample(truth, k), k * c.dt)
        arr = nav.arrays()
        n = len(arr["ekf_pos"])
        tpos = truth.pos[1 : n + 1]
        for key in ("ekf", "ins", "pf", "pmf"):
            pk = f"{key}_pos"
            if pk not in arr:
                continue
            err = np.linalg.norm(arr[pk] - tpos[: len(arr[pk])], axis=1)
            finals[key].append(float(err[-1]))
        est = nav.estimate("auto")
        print(
            f"run {i}: source={est.source} r1s={est.error_radius_1sigma:.1f}m "
            f"ekf={finals['ekf'][-1]:.1f}m"
        )
    return finals


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--npz", default=None, help="path to .npz with z + extent")
    p.add_argument("--n-runs", type=int, default=4)
    p.add_argument("--duration", type=float, default=60.0)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--no-pf", action="store_true")
    args = p.parse_args()

    terrain = _load_terrain(args.npz, args.seed)
    suit = terrain_suitability(terrain)
    print(f"suitability median={suit['median']:.3f} p10={suit['p10']:.3f}")

    cfg = SimConfig(
        duration=args.duration,
        seed=args.seed,
        use_pf=not args.no_pf,
        use_pmf=True,
        use_tercom=True,
        n_particles=min(800, SimConfig().n_particles),
    )

    if args.npz is None:
        # Fast path: package MC (always synthetic DEM inside evaluate).
        mc = run_montecarlo(cfg, n_runs=args.n_runs)
        print(mc.table())
        print("(tip: pass --npz to evaluate on a real tile instead of synthetic)")
        return 0

    finals = _run_on_terrain(cfg, terrain, args.n_runs)
    print("\nFinal error mean / p50:")
    for key, vals in finals.items():
        if not vals:
            continue
        a = np.asarray(vals)
        print(
            f"  {key:4s}  mean={a.mean():.1f}m  p50={np.percentile(a, 50):.1f}m  n={len(a)}"
        )
    # Last-run action authority snapshot (autonomy contract).
    c = replace(cfg, seed=cfg.seed + args.n_runs - 1)
    truth = generate_truth(c, terrain)
    nav = Navigator(c, terrain, truth.pos[0], truth.vel[0])
    imu = IMU(c, terrain)
    for k in range(1, len(truth)):
        nav.step(imu.sample(truth, k), k * c.dt)
    env = nav.action_envelope(t=c.duration)
    print(
        f"\naction envelope: confidence={env.confidence:.2f} binding={env.binding} "
        f"transit={env.permitted['transit']:.2f} rtb={env.permitted['rtb']:.2f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
