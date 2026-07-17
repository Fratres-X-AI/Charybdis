#!/usr/bin/env bash
# H200 SXM lane — max VRAM batch sizes, heavy hard eval focused on p95 tail.
set -euo pipefail
GPU_ID="${1:-0}"
LANE="${2:-e}"
REPO=/workspace/Charybdis
LOG="/tmp/pod_h200_lane${GPU_ID}.log"
: >"$LOG"

ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] h200 gpu${GPU_ID} lane=${LANE} $*" | tee -a "$LOG"; }

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
DST = ROOT / "models" / f"tcm_so2_h200_lane{gpu}.pt"
BEST = ROOT / "models" / f"tcm_so2_h200_best_lane{gpu}.pt"
if BEST.is_file():
    shutil.copy(BEST, DST)
    print(f"resume_best {BEST}", flush=True)
else:
    shutil.copy(SRC, DST)

# ep, n_samples, batch, n_terrains, lr, seed
if lane == "f":
    passes = [
        (20, 160_000, 8192, 20, 6.0e-5, 2201),
        (24, 220_000, 8192, 24, 4.0e-5, 2302),
        (28, 280_000, 8192, 28, 2.8e-5, 2403),
        (32, 340_000, 8192, 32, 2.0e-5, 2504),
        (36, 400_000, 8192, 36, 1.4e-5, 2605),
    ]
else:
    passes = [
        (18, 140_000, 8192, 18, 7.0e-5, 2101),
        (22, 200_000, 8192, 22, 5.0e-5, 2202),
        (26, 260_000, 8192, 26, 3.5e-5, 2303),
        (30, 320_000, 8192, 30, 2.5e-5, 2404),
        (34, 380_000, 8192, 34, 1.8e-5, 2505),
    ]

print(f"h200 lane={lane} device={torch.cuda.get_device_name(0)}", flush=True)
import subprocess
try:
    mem_mib = int(
        subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            text=True,
        ).strip().splitlines()[0]
    )
except Exception:
    mem_mib = 32768
if mem_mib >= 75000:
    train_bs = 8192
    infer_bs = 8192
elif mem_mib >= 40000:
    train_bs = 4096
    infer_bs = 4096
else:
    train_bs = 2048
    infer_bs = 2048
print(f"vram_mib={mem_mib} train_bs={train_bs} infer_bs={infer_bs}", flush=True)
passes = [(ep, ns, train_bs, nt, lr, seed) for ep, ns, _bs, nt, lr, seed in passes]
best_score = 1e9
best_pass = 0

for i, (ep, ns, bs, nt, lr, seed) in enumerate(passes, 1):
    t0 = time.time()
    print(f"H200 PASS {i}/{len(passes)} gpu={gpu} lane={lane} {ep}ep ns={ns} bs={bs}", flush=True)
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
    shutil.copy(DST, ROOT / "models" / f"tcm_so2_h200_lane{gpu}_pass{i:02d}.pt")
    print(f"train_wall_s={time.time()-t0:.1f}", flush=True)

    model = build_model()
    state = torch.load(DST, map_location="cuda", weights_only=True)
    model.load_state_dict(state)
    model.cuda().eval()
    terrains = [Terrain.synthetic(SimConfig(seed=seed + j)) for j in range(nt)]
    rng = np.random.default_rng(seed + 9999)
    hm = eval_hard(model, terrains, 350.0, "cuda", rng, n=32768, infer_batch=infer_bs)
    score = hm["after_mean"] + 0.35 * hm["after_p95"]
    print(
        f"eval gpu={gpu} lane={lane} pass={i} after_mean={hm['after_mean']:.1f}m "
        f"p50={hm['after_p50']:.0f} p95={hm['after_p95']:.0f} score={score:.1f} "
        f"imp={hm['improve_pct']:.0f}%",
        flush=True,
    )
    if score < best_score:
        best_score = score
        best_pass = i
        shutil.copy(DST, BEST)
        print(f"new_best gpu={gpu} lane={lane} pass={i} score={score:.1f}", flush=True)

model = build_model()
state = torch.load(BEST, map_location="cuda", weights_only=True)
model.load_state_dict(state)
model.cuda().eval()
terrains = [Terrain.synthetic(SimConfig(seed=j)) for j in range(48)]
rng = np.random.default_rng(42 + int(gpu))
final = eval_hard(model, terrains, 350.0, "cuda", rng, n=65536, infer_batch=infer_bs)
print(f"H200 FINAL gpu={gpu} lane={lane} best_pass={best_pass} {final}", flush=True)
PY

log "h200 lane complete"
