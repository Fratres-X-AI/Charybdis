#!/usr/bin/env bash
set -e
cd /workspace/Charybdis
source .venv/bin/activate
ts(){ date -u +"%H:%M:%S"; }
log(){ echo "[$(ts)] $*"; }

log "TRAIN NN ON GPU (vectorised data-gen, device=cuda)"
python - <<'PY'
import time, numpy as np, torch
from console.charybdis_nn import train, load_model, tcm_nn_match
from console import charybdis_core as core
assert torch.cuda.is_available()
t0=time.time()
train(model_path="models/tcm_cnn.pt", n_samples=120000, epochs=40, batch=4096, seed=0, device="cuda")
print(f"TRAIN wall={time.time()-t0:.1f}s dev=cuda {torch.cuda.get_device_name(0)}")
load_model("models/tcm_cnn.pt", device="cpu")
rng=np.random.default_rng(1); errs=[]
for _ in range(500):
    true=rng.uniform(15,110,size=2); est=true+rng.normal(0,4,size=2)
    corr,_,_=tcm_nn_match(true,est,core.bathymetry,model_path="models/tcm_cnn.pt")
    errs.append(float(np.linalg.norm(corr-true)))
print(f"NN mean_fix_err={np.mean(errs):.2f}m CEP50={np.percentile(errs,50):.2f}m CEP95={np.percentile(errs,95):.2f}m")
PY

log "final4 pytest x31"
python -m pytest tests/test_final4.py -q -n 31

log "benchmark"
PYTHONPATH=. python scripts/benchmark_15of15.py

log "DONE"
ls -la models/tcm_cnn.pt
echo 0 > /root/gpu.done
