#!/usr/bin/env bash
# One GPU training lane (5-pass hard SO2 ladder).
set -euo pipefail
GPU_ID="${1:-0}"
LANE="${2:-a}"
REPO=/workspace/Charybdis
LOG="/tmp/pod_gpu_lane${GPU_ID}.log"
: >"$LOG"

ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] gpu${GPU_ID} lane=${LANE} $*" | tee -a "$LOG"; }

cd "$REPO"
source .venv/bin/activate
export PYTHONPATH=.
export CUDA_VISIBLE_DEVICES="$GPU_ID"
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 MKL_NUM_THREADS=8
export PYTHONUNBUFFERED=1

log "probe $(python -c "import torch; print(torch.cuda.get_device_name(0))")"

python - <<PY | tee -a "$LOG"
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import numpy as np
import torch
from charybdis.config import SimConfig
from charybdis.experimental.nn_matcher import build_model, eval_hard, train
from charybdis.terrain import Terrain

gpu = os.environ.get("CUDA_VISIBLE_DEVICES", "0")
lane = "${LANE}"
ROOT = Path("/workspace/Charybdis")
SRC = ROOT / "models" / "tcm_so2.pt"
DST = ROOT / "models" / f"tcm_so2_lane{gpu}.pt"
BEST = ROOT / "models" / f"tcm_so2_best_lane{gpu}.pt"
if BEST.is_file():
    shutil.copy(BEST, DST)
    print(f"resume_best {BEST}", flush=True)
else:
    shutil.copy(SRC, DST)

if lane == "b":
    passes = [
        (18, 120_000, 4096, 16, 7.0e-5, 701),
        (22, 160_000, 4096, 20, 5.0e-5, 802),
        (26, 200_000, 4096, 24, 3.5e-5, 903),
        (30, 240_000, 4096, 28, 2.5e-5, 1004),
        (34, 280_000, 4096, 32, 1.8e-5, 1105),
    ]
elif lane == "c":
    passes = [
        (16, 110_000, 3072, 15, 7.5e-5, 1201),
        (21, 150_000, 4096, 19, 5.5e-5, 1303),
        (24, 170_000, 4096, 21, 4.8e-5, 1404),
        (29, 230_000, 4096, 27, 2.8e-5, 1505),
        (33, 270_000, 4096, 30, 2.2e-5, 1606),
    ]
elif lane == "d":
    passes = [
        (19, 130_000, 4096, 17, 6.5e-5, 1701),
        (23, 170_000, 4096, 21, 4.8e-5, 1802),
        (27, 210_000, 4096, 25, 3.2e-5, 1903),
        (31, 250_000, 4096, 29, 2.3e-5, 2004),
        (36, 300_000, 4096, 34, 1.6e-5, 2105),
    ]
else:
    passes = [
        (15, 100_000, 3072, 14, 8.0e-5, 201),
        (20, 140_000, 4096, 18, 6.0e-5, 1302),
        (25, 180_000, 4096, 22, 4.5e-5, 403),
        (28, 220_000, 4096, 26, 3.0e-5, 504),
        (32, 260_000, 4096, 32, 2.0e-5, 605),
    ]

print(f"lane={lane} device={torch.cuda.get_device_name(0)}", flush=True)
best_after = 1e9
best_pass = 0

for i, (ep, ns, bs, nt, lr, seed) in enumerate(passes, 1):
    t0 = time.time()
    print(f"PASS {i}/{len(passes)} gpu={gpu} lane={lane} {ep}ep ns={ns} bs={bs}", flush=True)
    train(
        epochs=ep,
        n_samples=ns,
        batch=bs,
        seed=seed,
        device="cuda",
        n_terrains=nt,
        resume=str(DST),
        lr=lr,
        hard=True,
        model_path=str(DST),
    )
    shutil.copy(DST, ROOT / "models" / f"tcm_so2_lane{gpu}_pass{i:02d}.pt")
    print(f"train_wall_s={time.time()-t0:.1f}", flush=True)

    model = build_model()
    state = torch.load(DST, map_location="cuda", weights_only=True)
    model.load_state_dict(state)
    model.cuda().eval()
    terrains = [Terrain.synthetic(SimConfig(seed=seed + j)) for j in range(nt)]
    rng = np.random.default_rng(seed + 9999)
    hm = eval_hard(model, terrains, 350.0, "cuda", rng, n=16384, infer_batch=2048)
    print(
        f"eval gpu={gpu} lane={lane} pass={i} after_mean={hm['after_mean']:.1f}m "
        f"p50={hm['after_p50']:.0f} p95={hm['after_p95']:.0f} imp={hm['improve_pct']:.0f}%",
        flush=True,
    )
    if hm["after_mean"] < best_after:
        best_after = hm["after_mean"]
        best_pass = i
        shutil.copy(DST, BEST)
        print(f"new_best gpu={gpu} lane={lane} pass={i}", flush=True)

model = build_model()
state = torch.load(BEST, map_location="cuda", weights_only=True)
model.load_state_dict(state)
model.cuda().eval()
terrains = [Terrain.synthetic(SimConfig(seed=j)) for j in range(32)]
rng = np.random.default_rng(42 + int(gpu))
final = eval_hard(model, terrains, 350.0, "cuda", rng, n=32768, infer_batch=2048)
print(f"FINAL gpu={gpu} lane={lane} best_pass={best_pass} {final}", flush=True)
PY

log "lane complete"
