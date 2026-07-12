#!/usr/bin/env bash
# Max out RTX 4090: escalating hard SO(2) training + large-batch stress evals.
set -euo pipefail
REPO=/workspace/Charybdis
LOG=/tmp/pod_max_gpu.log
: >"$LOG"
cd "$REPO"
source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 MKL_NUM_THREADS=8
export PYTHONUNBUFFERED=1

ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

log "install torch cu126"
pip install -q torch --index-url https://download.pytorch.org/whl/cu126

log "GPU probe"
python - <<'PY' | tee -a "$LOG"
import torch
assert torch.cuda.is_available(), "CUDA required"
name = torch.cuda.get_device_name(0)
cap = torch.cuda.get_device_capability(0)
props = torch.cuda.get_device_properties(0)
a = torch.randn(4096, 4096, device="cuda")
b = torch.randn(4096, 4096, device="cuda")
_ = (a @ b).sum().item()
torch.cuda.synchronize()
print(f"gpu_ok name={name} cap={cap} vram_gb={props.total_memory/1e9:.1f}")
PY

mkdir -p models
if [[ ! -f models/tcm_so2.pt ]]; then
  log "ERROR missing models/tcm_so2.pt"
  exit 1
fi

log "start 4090 max ladder"
python - <<'PY' | tee -a "$LOG"
from __future__ import annotations

import shutil
import time
from pathlib import Path

import numpy as np
import torch
from charybdis.config import SimConfig
from charybdis.experimental.nn_matcher import build_model, eval_hard, train
from charybdis.terrain import Terrain

ROOT = Path("/workspace/Charybdis")
DST = ROOT / "models" / "tcm_so2.pt"
PASSES = [
    (15, 100_000, 3072, 14, 8.0e-5, 201),
    (20, 140_000, 4096, 18, 6.0e-5, 302),
    (25, 180_000, 4096, 22, 4.5e-5, 403),
    (28, 220_000, 4096, 26, 3.0e-5, 504),
    (32, 260_000, 4096, 32, 2.0e-5, 605),
]

print(f"device={torch.cuda.get_device_name(0)}", flush=True)
best_after = 1e9
best_pass = 0

for i, (ep, ns, bs, nt, lr, seed) in enumerate(PASSES, 1):
    t0 = time.time()
    print(
        f"\n=== PASS {i}/{len(PASSES)}: {ep}ep x {ns} @{bs} terr={nt} lr={lr:.1e} hard ===",
        flush=True,
    )
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
    shutil.copy(DST, ROOT / "models" / f"tcm_so2_pass{i:02d}.pt")
    wall = time.time() - t0
    print(f"train_wall_s={wall:.1f}", flush=True)

    model = build_model()
    state = torch.load(DST, map_location="cuda", weights_only=True)
    model.load_state_dict(state)
    model.cuda().eval()
    terrains = [Terrain.synthetic(SimConfig(seed=seed + j)) for j in range(nt)]
    rng = np.random.default_rng(seed + 9999)
    hm = eval_hard(model, terrains, 350.0, "cuda", rng, n=16384, infer_batch=2048)
    print(
        f"eval pass={i} after_mean={hm['after_mean']:.1f}m p50={hm['after_p50']:.0f} "
        f"p95={hm['after_p95']:.0f} imp={hm['improve_pct']:.0f}%",
        flush=True,
    )
    if hm["after_mean"] < best_after:
        best_after = hm["after_mean"]
        best_pass = i
        shutil.copy(DST, ROOT / "models" / "tcm_so2_best.pt")
        print(f"new_best pass={i}", flush=True)

print(f"\n=== FINAL mega-eval best_pass={best_pass} ===", flush=True)
model = build_model()
state = torch.load(ROOT / "models" / "tcm_so2_best.pt", map_location="cuda", weights_only=True)
model.load_state_dict(state)
model.cuda().eval()
terrains = [Terrain.synthetic(SimConfig(seed=j)) for j in range(32)]
rng = np.random.default_rng(42)
final = eval_hard(model, terrains, 350.0, "cuda", rng, n=32768, infer_batch=2048)
print(f"FINAL {final}", flush=True)
shutil.copy(ROOT / "models" / "tcm_so2_best.pt", DST)
print("saved models/tcm_so2.pt", flush=True)
PY

log "4090 max ladder complete"
