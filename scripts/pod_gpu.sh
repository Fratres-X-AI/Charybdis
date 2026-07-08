#!/usr/bin/env bash
set -e
cd /workspace 2>/dev/null || cd ~
ts(){ date -u +"%H:%M:%S"; }
log(){ echo "[$(ts)] $*"; }

log "clone/update Charybdis"
if [ -d Charybdis/.git ]; then
  cd Charybdis && git fetch -q origin main && git checkout -q main && git reset -q --hard origin/main
else
  git clone -q https://github.com/Fratres-X-AI/Charybdis.git && cd Charybdis
fi
git log --oneline -1

log "venv + deps"
python3 -m venv .venv
source .venv/bin/activate
pip install -q -U pip
pip install -q numpy scipy matplotlib pandas pytest pytest-xdist

log "torch cu124 (stable, Ada sm_89)"
pip install -q torch --index-url https://download.pytorch.org/whl/cu124

log "GPU compute verify (real matmul kernel)"
python - <<'PY'
import torch
assert torch.cuda.is_available(), "no CUDA"
dev = torch.cuda.get_device_name(0)
a = torch.randn(2048, 2048, device="cuda")
b = torch.randn(2048, 2048, device="cuda")
c = (a @ b).sum().item()
print(f"GPU OK: {dev}  matmul_sum={c:.1f}  cc={torch.cuda.get_device_capability(0)}")
PY

log "base pytest x31"
export OMP_NUM_THREADS=8
python -m pytest -q --ignore=tests/test_final4.py -n 31

log "TRAIN NN ON GPU (device=cuda)"
python - <<'PY'
import time, torch
from charybdis_nn import train, load_model, tcm_nn_match
import charybdis_core as core
import numpy as np
assert torch.cuda.is_available()
t0 = time.time()
train(model_path="models/tcm_cnn.pt", n_samples=60000, epochs=25, batch=2048, seed=0, device="cuda", num_workers=16)
print(f"train wall={time.time()-t0:.1f}s")
load_model("models/tcm_cnn.pt", device="cpu")
errs=[]
rng=np.random.default_rng(1)
for _ in range(400):
    true=rng.uniform(15,110,size=2); est=true+rng.normal(0,4,size=2)
    corr,_,_=tcm_nn_match(true,est,core.bathymetry,model_path="models/tcm_cnn.pt")
    errs.append(float(np.linalg.norm(corr-true)))
print(f"NN mean fix err={np.mean(errs):.2f}m  CEP50={np.percentile(errs,50):.2f}m")
PY

log "final4 pytest x31"
python -m pytest tests/test_final4.py -q -n 31

log "benchmark"
PYTHONPATH=. python scripts/benchmark_15of15.py

log "DONE"
ls -la models/tcm_cnn.pt
