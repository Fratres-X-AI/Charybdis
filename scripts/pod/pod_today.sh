#!/usr/bin/env bash
# Charybdis "done today" validation on RunPod (serial pytest + 31-worker MC only).
#
# Usage (on pod after clone):
#   bash scripts/pod/pod_today.sh                  # synthetic MC
#   bash scripts/pod/pod_today.sh /path/tile.npz   # real bathy tile
#
# Optional env:
#   TODAY_TRAIN=1     retrain GDI SO(2) matcher (GPU)
#   STRESS_SEEDS=64   stress harness seeds (default 64)
#   MC_RUNS=31        MC runs (default 31, hard cap 31)
set -euo pipefail

REPO="${REPO:-/workspace/Charybdis}"
NPZ="${1:-}"
STRESS_SEEDS="${STRESS_SEEDS:-64}"
MC_RUNS="${MC_RUNS:-31}"
if (( MC_RUNS > 31 )); then
  echo "MC_RUNS capped at 31 (hard rule)" >&2
  MC_RUNS=31
fi

ts(){ date -u +"%H:%M:%S"; }
log(){ echo "[$(ts)] $*" | tee -a "${REPO}/pod_today.log"; }

cd "${REPO}"
mkdir -p models

export PYTHONPATH="${REPO}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export MPLBACKEND=Agg

if [ ! -d .venv ]; then
  log "creating venv"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -U pip
pip install -q -r requirements.txt

log "=== PHASE 1: CI-fast pytest (skip slow) ==="
GITHUB_ACTIONS=true python -m pytest -q --timeout=120 --timeout-method=thread \
  | tee -a pod_today.log

log "=== PHASE 2: full pytest (RUN_SLOW=1, serial) ==="
RUN_SLOW=1 python -m pytest -q --timeout=120 --timeout-method=thread \
  | tee -a pod_today.log

log "=== PHASE 3: stress harness (${STRESS_SEEDS} seeds, 31 workers) ==="
python scripts/stress_run.py "${STRESS_SEEDS}" | tee -a pod_today.log

log "=== PHASE 4: Monte Carlo (${MC_RUNS} runs, 120s) ==="
if [ -n "${NPZ}" ]; then
  python scripts/mc_real_region.py --npz "${NPZ}" --n-runs "${MC_RUNS}" --duration 120 \
    | tee -a pod_today.log
else
  python scripts/mc_real_region.py --n-runs "${MC_RUNS}" --duration 120 \
    | tee -a pod_today.log
fi

if [ "${TODAY_TRAIN:-0}" = "1" ]; then
  log "=== PHASE 5: GPU NN train (optional) ==="
  pip install -q torch --index-url https://download.pytorch.org/whl/cu126 || true
  bash scripts/pod/nn_train_gpu.sh | tee -a pod_today.log
else
  log "=== PHASE 5: NN hard eval (skip train; set TODAY_TRAIN=1 to retrain) ==="
  if python -c "import torch" 2>/dev/null && [ -f models/tcm_so2.pt ]; then
    python - <<'PY' | tee -a pod_today.log
from charybdis.experimental.nn_matcher import eval_hard
print(eval_hard("models/tcm_so2.pt", n=4096))
PY
  else
    log "skip NN eval (no torch or models/tcm_so2.pt)"
  fi
fi

log "=== PHASE 6: UUV benchmarks (informational) ==="
python scripts/benchmark_15of15.py | tee -a pod_today.log || true

log "=== DONE ==="
echo "PASS" > pod_today.exit
log "log: ${REPO}/pod_today.log"
