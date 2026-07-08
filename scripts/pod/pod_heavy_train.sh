#!/usr/bin/env bash
set -e
cd /workspace/Charybdis
. .venv/bin/activate
export PYTHONPATH=. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
exec > /root/so2_heavy.log 2>&1
echo "=== start $(date -u) ==="
python - <<'PY'
import numpy as np
import torch
from charybdis import SimConfig, Terrain
from charybdis.experimental.nn_matcher import train, load_model, match_position

print("cuda", torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu")

print("=== SO2 heavy pass 1: 20 epochs x 80k @ batch 1024 ===")
train(epochs=20, n_samples=80000, batch=1024, seed=42, device="cuda")

print("=== SO2 heavy pass 2: 10 epochs x 40k @ batch 1024, seed 7 ===")
train(epochs=10, n_samples=40000, batch=1024, seed=7, device="cuda")

print("=== validation ===")
load_model("models/tcm_so2.pt", device="cuda")
rng = np.random.default_rng(99)
terr = Terrain.synthetic(SimConfig(seed=99))
errs, suits = [], []
for i in range(32):
    true = rng.uniform(2000, 30000, size=2)
    est = true + rng.normal(0, 90.0, size=2)
    pos, suit = match_position(true, est, terr)
    errs.append(float(np.linalg.norm(pos - true)))
    suits.append(float(suit))
print(f"val n=32 mean_err={np.mean(errs):.1f}m p50={np.percentile(errs,50):.1f}m suit_mean={np.mean(suits):.3f}")
print("=== done $(date -u) ===")
PY
echo "=== finish $(date -u) ==="
