#!/usr/bin/env bash
# Integration-grade validation — pod only (31 workers max).
set -euo pipefail
REPO=/workspace/Charybdis
cd "$REPO"
LOG=/tmp/pod_integration_grade.log
: >"$LOG"
ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export MPLBACKEND=Agg

log "=== Phase 1: fast pytest (replay + patrol + contracts) ==="
python -m pytest --timeout=120 --timeout-method=thread \
  tests/test_hybrid_replay.py \
  tests/test_hybrid_patrol_handoffs.py \
  tests/test_hybrid_deep_validation.py -m "not slow" -q 2>&1 | tee -a "$LOG"
log "PHASE1_OK"

log "=== Phase 2: deep engineering 64x7 @ 31 workers (includes long_blackout) ==="
python -m pytest tests/test_hybrid_deep_validation.py::test_deep_engineering_matrix_passes_locally -q 2>&1 | tee -a "$LOG"
log "PHASE2_OK"

log "INTEGRATION_GRADE_COMPLETE"
