#!/usr/bin/env bash
set -e
cd /workspace/Charybdis
. .venv/bin/activate
export PYTHONPATH=. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
exec >> /root/so2_tune.log 2>&1
echo "=== pass 5 $(date -u) ==="
python - <<'PY'
import torch
from charybdis.experimental.nn_matcher import train, eval_hard, load_model, build_model
from charybdis.config import SimConfig
from charybdis.terrain import Terrain
import numpy as np

print("cuda", torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu")
print("=== pass 5: 25 epochs x 120k @2048 hard eval hard train ===")
train(epochs=25, n_samples=120000, batch=2048, seed=500, device="cuda",
      n_terrains=20, resume="models/tcm_so2.pt", lr=8e-5, hard=True)
print("=== final hard eval ===")
m = build_model()
import torch as T
m.load_state_dict(T.load("models/tcm_so2.pt", map_location="cuda", weights_only=True))
m.cuda().eval()
terrains = [Terrain.synthetic(SimConfig(seed=i)) for i in range(24)]
rng = np.random.default_rng(999)
hm = eval_hard(m, terrains, 350.0, "cuda", rng, n=8192, infer_batch=1024)
print("FINAL", hm)
PY
echo "=== pass 5 done $(date -u) ==="
