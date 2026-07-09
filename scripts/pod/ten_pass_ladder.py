#!/usr/bin/env python3
"""10-pass escalating hard SO(2) training — run on RunPod A100 only."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import numpy as np
import torch
from charybdis.config import SimConfig
from charybdis.terrain import Terrain
from charybdis.experimental.nn_matcher import build_model, eval_hard, train

PASSES = [
    (12, 60_000, 2048, 12, 1.0e-4, 101),
    (15, 80_000, 2048, 14, 8.0e-5, 202),
    (18, 100_000, 3072, 16, 7.0e-5, 303),
    (20, 120_000, 3072, 18, 6.0e-5, 404),
    (22, 140_000, 4096, 20, 5.5e-5, 505),
    (25, 160_000, 4096, 22, 5.0e-5, 606),
    (28, 180_000, 4096, 24, 4.0e-5, 707),
    (30, 200_000, 4096, 26, 3.5e-5, 808),
    (32, 220_000, 4096, 28, 2.5e-5, 909),
    (35, 250_000, 4096, 32, 2.0e-5, 1010),
]


def main() -> None:
    log = open("ten_pass.log", "a", buffering=1)

    def p(msg: str) -> None:
        print(msg, flush=True)
        log.write(msg + "\n")

    Path("models").mkdir(exist_ok=True)
    src = Path("charybdis/models/tcm_so2.pt")
    dst = Path("models/tcm_so2.pt")
    if src.is_file():
        shutil.copy(src, dst)

    p(f"=== 10-PASS LADDER start ===")
    p(f"gpu {torch.cuda.get_device_name(0)}")

    best_after = 1e9
    best_pass = 0

    for i, (ep, ns, bs, nt, lr, seed) in enumerate(PASSES, 1):
        p(f"\n{'=' * 60}\nPASS {i}/10: {ep}ep x {ns} @{bs} terr={nt} lr={lr:.1e} hard\n{'=' * 60}")
        train(
            epochs=ep, n_samples=ns, batch=bs, seed=seed, device="cuda",
            n_terrains=nt, resume=str(dst), lr=lr, hard=True, model_path=str(dst),
        )
        shutil.copy(dst, f"models/tcm_so2_pass{i:02d}.pt")

        m = build_model()
        m.load_state_dict(torch.load(dst, map_location="cuda", weights_only=True))
        m.cuda().eval()
        terrains = [Terrain.synthetic(SimConfig(seed=seed + j)) for j in range(nt)]
        rng = np.random.default_rng(seed + 9999)
        hm = eval_hard(m, terrains, 350.0, "cuda", rng, n=8192, infer_batch=1024)
        p(
            f"PASS {i} EVAL after_mean={hm['after_mean']:.1f}m p50={hm['after_p50']:.0f} "
            f"p95={hm['after_p95']:.0f} imp={hm['improve_pct']:.0f}%"
        )
        if hm["after_mean"] < best_after:
            best_after = hm["after_mean"]
            best_pass = i
            shutil.copy(dst, "models/tcm_so2_best.pt")
            p(f"  -> new best checkpoint (pass {i})")

    p(f"\n=== FINAL EVAL best pass {best_pass} after_mean={best_after:.1f}m n=16384 ===")
    m = build_model()
    m.load_state_dict(torch.load("models/tcm_so2_best.pt", map_location="cuda", weights_only=True))
    m.cuda().eval()
    terrains = [Terrain.synthetic(SimConfig(seed=i)) for i in range(32)]
    rng = np.random.default_rng(42)
    final = eval_hard(m, terrains, 350.0, "cuda", rng, n=16384, infer_batch=1024)
    p(f"FINAL {final}")
    shutil.copy("models/tcm_so2_best.pt", dst)
    shutil.copy(dst, "charybdis/models/tcm_so2.pt")
    p("saved models/tcm_so2.pt")
    p("=== 10-PASS LADDER done ===")
    log.close()


if __name__ == "__main__":
    main()
