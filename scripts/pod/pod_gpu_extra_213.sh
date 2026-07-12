#!/usr/bin/env bash
# Optional GPU extras while pod is warm: NN hard eval if model present.
set -euo pipefail
REPO=/workspace/Charybdis
LOG=/tmp/pod_gpu_extra.log
: >"$LOG"
cd "$REPO"
source .venv/bin/activate
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export MPLBACKEND=Agg

ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

log "GPU extras on $(nvidia-smi -L)"

if [[ -f models/tcm_so2.pt ]]; then
  log "NN hard eval"
  python - <<'PY' | tee -a "$LOG"
from charybdis.experimental.nn_matcher import eval_hard
print(eval_hard("models/tcm_so2.pt", n=4096))
PY
else
  log "skip NN eval (no models/tcm_so2.pt)"
fi

log "benchmark sweep"
python scripts/benchmark_15of15.py | tee -a "$LOG" || true

log "GPU extras complete"
