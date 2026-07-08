#!/usr/bin/env bash
set -e
cd /workspace/Charybdis
. .venv/bin/activate
export PYTHONPATH=. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1

while pgrep -f 'pip install.*torch' >/dev/null 2>&1; do
  echo "[wait] torch pip still running..."
  sleep 10
done

python - <<'PY'
import torch
print("torch", torch.__version__, "cuda", torch.cuda.is_available())
if torch.cuda.is_available():
    print("gpu", torch.cuda.get_device_name(0))
PY

echo "[train] SO(2) matcher on GPU"
python - <<'PY'
from charybdis.experimental.nn_matcher import train
train(epochs=6, n_samples=8000, batch=256, device="cuda")
PY

ls -la models/tcm_so2.pt

python - <<'PY'
from charybdis.experimental.nn_matcher import load_model
load_model("models/tcm_so2.pt", device="cuda")
print("load OK")
PY

echo "[done] tcm_so2.pt ready"
