#!/usr/bin/env bash
# Re-run Jul 15 lost pod validation day: metric sprint -> max_out -> mission -> release -> worst.
set -euo pipefail

REPO=/workspace/Charybdis
LOG=/tmp/pod_recover_day.log
: >"$LOG"

ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

cd "$REPO"
log "RECOVER_DAY_START pod=${POD_NAME:-unknown} cpus=$(nproc) gpus=$(nvidia-smi -L 2>/dev/null | wc -l)"
log "HEAD $(git rev-parse --short HEAD 2>/dev/null || echo synced)"

bash scripts/pod/pod_bootstrap_venv.sh 2>&1 | tee -a "$LOG"
source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 MPLBACKEND=Agg

log "=== 1/5 metric sprint (highres + integration 31+31) ==="
bash scripts/pod/pod_metric_sprint.sh 2>&1 | tee -a "$LOG"
log "METRIC_SPRINT_DONE"

log "=== 2/5 max_out (release 256 + worst 512 @ 31 workers) ==="
bash scripts/pod/pod_max_out.sh 2>&1 | tee -a "$LOG"
log "MAX_OUT_DONE"

log "=== 3/5 mission engineering matrix @ 31 workers ==="
python scripts/hybrid_validate_mission_matrix.py \
  --tier engineering \
  --runs 64 \
  --workers 31 \
  --allow-dirty 2>&1 | tee -a "$LOG"
log "MISSION_DONE"

log "=== 4/5 release grade harbor+deep 256 @ 31+31 ==="
bash scripts/pod/pod_release_grade.sh 2>&1 | tee -a "$LOG"
log "RELEASE_GRADE_DONE"

log "=== 5/5 worst sweep harbor+deep 512 @ 31+31 ==="
bash scripts/pod/pod_worst_sweep.sh 2>&1 | tee -a "$LOG"
log "WORST_SWEEP_DONE"

log "RECOVER_DAY_COMPLETE"
