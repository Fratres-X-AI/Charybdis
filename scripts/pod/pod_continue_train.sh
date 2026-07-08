#!/usr/bin/env bash
set -e
cd /workspace/Charybdis
. .venv/bin/activate
export PYTHONPATH=. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
exec >> /root/so2_tune.log 2>&1
echo "=== continue $(date -u) ==="
python - <<'PY'
import numpy as np
import torch
from charybdis import SimConfig, Terrain
from charybdis.experimental.nn_matcher import train, load_model, match_position

print("cuda", torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu")

print("=== continue pass 3: 35 epochs x 100k @512, lr=1e-4 ===")
train(epochs=35, n_samples=100000, batch=512, seed=200, device="cuda",
      n_terrains=16, resume="models/tcm_so2.pt", lr=1e-4)

print("=== continue pass 4: 20 epochs x 50k @512, lr=4e-5 ===")
train(epochs=20, n_samples=50000, batch=512, seed=300, device="cuda",
      n_terrains=16, resume="models/tcm_so2.pt", lr=4e-5)

print("=== validation ===")
load_model("models/tcm_so2.pt", device="cuda")
rng = np.random.default_rng(456)
terrains = [Terrain.synthetic(SimConfig(seed=i)) for i in range(12)]
errs_before, errs_after = [], []
for terr in terrains:
    for _ in range(20):
        true = rng.uniform(2500, 32000, size=2)
        est = true + rng.normal(0, 75.0, size=2)
        errs_before.append(float(np.linalg.norm(est - true)))
        pos, _ = match_position(true, est, terr)
        errs_after.append(float(np.linalg.norm(pos - true)))
print(f"before_mean={np.mean(errs_before):.1f}m after_mean={np.mean(errs_after):.1f}m p50={np.percentile(errs_after,50):.1f}m p90={np.percentile(errs_after,90):.1f}m")
PY
echo "=== continue done $(date -u) ==="
