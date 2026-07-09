#!/usr/bin/env bash
# Run phases 3-6 only (stress + MC + NN eval + benchmark).
set -euo pipefail
cd /workspace/Charybdis
source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export MPLBACKEND=Agg

ts(){ date -u +"%H:%M:%S"; }
log(){ echo "[$(ts)] $*" | tee -a pod_today.log; }

log "=== PHASE 3: stress harness (64 seeds) ==="
python scripts/stress_run.py 64 | tee -a pod_today.log

log "=== PHASE 4: Monte Carlo (31 runs) ==="
python scripts/mc_real_region.py --n-runs 31 --duration 120 | tee -a pod_today.log

log "=== PHASE 5: NN hard eval ==="
if pip install -q torch --index-url https://download.pytorch.org/whl/cu126 2>/dev/null \
   && [ -f models/tcm_so2.pt ]; then
  python - <<'PY' | tee -a pod_today.log
from charybdis.experimental.nn_matcher import eval_hard
print(eval_hard("models/tcm_so2.pt", n=4096))
PY
else
  log "skip NN eval"
fi

log "=== PHASE 6: benchmarks ==="
python scripts/benchmark_15of15.py | tee -a pod_today.log || true

log "=== DONE ==="
echo "PASS" > pod_today.exit
