#!/usr/bin/env bash
# Metric improvement sprint: highres bathy + integration engineering (pod only).
set -euo pipefail
REPO=/workspace/Charybdis
cd "$REPO"
LOG=/tmp/pod_metric_sprint.log
: >"$LOG"
ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export MPLBACKEND=Agg

log "pod=${POD_NAME:-unknown} sha=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
log "gpus=$(nvidia-smi -L 2>/dev/null | wc -l) cpus=$(nproc)"

log "=== highres NOAA bathymetry (engineering + release) ==="
bash scripts/pod/pod_highres_bathy.sh 2>&1 | tee -a "$LOG"

log "=== integration engineering harbor+deep ==="
bash scripts/pod/pod_integration_grade.sh 2>&1 | tee -a "$LOG"

log "METRIC_SPRINT_COMPLETE"
