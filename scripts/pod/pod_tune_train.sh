#!/usr/bin/env bash
set -e
cd /workspace/Charybdis
. .venv/bin/activate
export PYTHONPATH=. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
exec > /root/so2_tune.log 2>&1
echo "=== tune start $(date -u) ==="
python - <<'PY'
import numpy as np
import torch
from charybdis import SimConfig, Terrain
from charybdis.experimental.nn_matcher import SPAN, build_model, train, load_model, match_position

print("cuda", torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu")
print("params", sum(p.numel() for p in build_model().parameters()))

print("=== tuned train pass 1 ===")
train(epochs=25, n_samples=60000, batch=512, seed=42, device="cuda", n_terrains=12)

print("=== tuned train pass 2 fine-tune ===")
train(epochs=12, n_samples=30000, batch=512, seed=99, device="cuda", n_terrains=12)

print("=== validation ===")
load_model("models/tcm_so2.pt", device="cuda")
rng = np.random.default_rng(123)
terrains = [__import__("charybdis.terrain", fromlist=["Terrain"]).Terrain.synthetic(SimConfig(seed=i)) for i in range(8)]
errs_before, errs_after, suits = [], [], []
for terr in terrains:
    for _ in range(16):
        true = rng.uniform(2500, 32000, size=2)
        est = true + rng.normal(0, 75.0, size=2)
        errs_before.append(float(np.linalg.norm(est - true)))
        pos, suit = match_position(true, est, terr)
        errs_after.append(float(np.linalg.norm(pos - true)))
        suits.append(float(suit))
print(f"before_mean={np.mean(errs_before):.1f}m after_mean={np.mean(errs_after):.1f}m p50_after={np.percentile(errs_after,50):.1f}m suit={np.mean(suits):.3f}")
PY
echo "=== tune finish $(date -u) ==="
