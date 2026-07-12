#!/usr/bin/env bash
# Dual 2x4090 sprint: Phase 1, then harbor + deep matrices in parallel.
set -euo pipefail

REPO=/workspace/Charybdis
LOG=/tmp/pod_dual_sprint.log
HARBOR_LOG=/tmp/pod_harbor_matrix.log
DEEP_LOG=/tmp/pod_deep_matrix.log

ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

: >"$LOG"
cd "$REPO"
log "dual sprint HEAD $(git rev-parse --short HEAD 2>/dev/null || echo synced-tree)"
log "gpus: $(nvidia-smi -L 2>/dev/null || echo none)"

if [[ ! -d .venv ]]; then
  log "create venv"
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install -q -U pip
log "install ci deps"
python -m pip install -q -c requirements/ci.txt -e ".[dev]"

log "=== PHASE 1 pod acceptance ==="
bash scripts/pod/phase1_pod.sh 2>&1 | tee -a "$LOG"
log "PHASE1_DONE"

STAMP=$(date -u +"%Y%m%dT%H%M%SZ")
SHA=$(git rev-parse --short HEAD 2>/dev/null || echo nosha)
OUT_BASE="artifacts/validation/${STAMP}-${SHA}"

log "=== PHASE 2 parallel: harbor + deep engineering (64 seeds) ==="
(
  python scripts/hybrid_validate_matrix.py \
    --tier engineering \
    --runs 64 \
    --workers 31 \
    --allow-dirty \
    --output-dir "${OUT_BASE}/engineering" \
    2>&1 | tee "$HARBOR_LOG"
  echo "HARBOR_ENG_DONE" >>"$HARBOR_LOG"
) &
PID_H=$!

(
  python scripts/hybrid_validate_deep_matrix.py \
    --tier engineering \
    --runs 64 \
    --workers 31 \
    --allow-dirty \
    --output-dir "${OUT_BASE}/deep_engineering" \
    2>&1 | tee "$DEEP_LOG"
  echo "DEEP_ENG_DONE" >>"$DEEP_LOG"
) &
PID_D=$!

wait "$PID_H" "$PID_D"
log "PHASE2_ENG_DONE"

log "=== PHASE 2 parallel: harbor + deep release (256 seeds) ==="
(
  python scripts/hybrid_validate_matrix.py \
    --tier release \
    --runs 256 \
    --workers 31 \
    --allow-dirty \
    --output-dir "${OUT_BASE}/release" \
    2>&1 | tee -a "$HARBOR_LOG"
  echo "HARBOR_REL_DONE" >>"$HARBOR_LOG"
) &
PID_H=$!

(
  python scripts/hybrid_validate_deep_matrix.py \
    --tier release \
    --runs 256 \
    --workers 31 \
    --allow-dirty \
    --output-dir "${OUT_BASE}/deep_release" \
    2>&1 | tee -a "$DEEP_LOG"
  echo "DEEP_REL_DONE" >>"$DEEP_LOG"
) &
PID_D=$!

wait "$PID_H" "$PID_D"
log "PHASE2_REL_DONE"

log "=== DUAL SPRINT COMPLETE ==="
log "artifacts ${OUT_BASE}"
