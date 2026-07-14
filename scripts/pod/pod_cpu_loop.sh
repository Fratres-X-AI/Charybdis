#!/usr/bin/env bash
# Continuous CPU validation loop — release -> worst sweep -> integration, repeat.
set -euo pipefail
REPO=/workspace/Charybdis
cd "$REPO"
LOG=/tmp/pod_cpu_loop.log
: >"$LOG"
ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export MPLBACKEND=Agg

cycle=0
while true; do
  cycle=$((cycle + 1))
  log "LOOP_CYCLE=${cycle} release_grade"
  bash scripts/pod/pod_release_grade.sh 2>&1 | tee -a "$LOG"
  log "LOOP_CYCLE=${cycle} worst_sweep"
  bash scripts/pod/pod_worst_sweep.sh 2>&1 | tee -a "$LOG"
  log "LOOP_CYCLE=${cycle} integration_grade"
  bash scripts/pod/pod_integration_grade.sh 2>&1 | tee -a "$LOG"
  log "LOOP_CYCLE=${cycle} complete"
done
