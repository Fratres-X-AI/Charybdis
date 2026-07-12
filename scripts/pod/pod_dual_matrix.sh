#!/usr/bin/env bash
# Run harbor + deep validation matrices in parallel (31 workers each).
set -euo pipefail

REPO=/workspace/Charybdis
LOG=/tmp/pod_dual_matrix.log
HARBOR_LOG=/tmp/pod_harbor_matrix.log
DEEP_LOG=/tmp/pod_deep_matrix.log

ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

: >"$LOG"
cd "$REPO"
source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1

NUMA0=""
NUMA1=""
if command -v numactl >/dev/null 2>&1; then
  if numactl --hardware 2>/dev/null | grep -q "node 1"; then
    NUMA0="numactl --cpunodebind=0 --membind=0"
    NUMA1="numactl --cpunodebind=1 --membind=1"
    log "numa split: harbor=node0 deep=node1"
  fi
fi

TIER="${1:-engineering}"
RUNS="${2:-64}"
STAMP=$(date -u +"%Y%m%dT%H%M%SZ")
SHA=$(git rev-parse --short HEAD 2>/dev/null || echo synced)
OUT_BASE="artifacts/validation/${STAMP}-${SHA}"

log "dual matrix tier=${TIER} runs=${RUNS} cpus=$(nproc) workers=31+31"
log "HEAD ${SHA}"

if [[ "$TIER" == "engineering" ]]; then
  H_OUT="${OUT_BASE}/engineering"
  D_OUT="${OUT_BASE}/deep_engineering"
else
  H_OUT="${OUT_BASE}/release"
  D_OUT="${OUT_BASE}/deep_release"
fi

log "=== PARALLEL START harbor=${H_OUT} deep=${D_OUT} ==="
(
  $NUMA0 python scripts/hybrid_validate_matrix.py \
    --tier "$TIER" \
    --runs "$RUNS" \
    --workers 31 \
    --allow-dirty \
    --output-dir "$H_OUT" \
    2>&1 | tee "$HARBOR_LOG"
  echo "HARBOR_${TIER^^}_DONE" >>"$HARBOR_LOG"
) &
PID_H=$!

(
  $NUMA1 python scripts/hybrid_validate_deep_matrix.py \
    --tier "$TIER" \
    --runs "$RUNS" \
    --workers 31 \
    --allow-dirty \
    --output-dir "$D_OUT" \
    2>&1 | tee "$DEEP_LOG"
  echo "DEEP_${TIER^^}_DONE" >>"$DEEP_LOG"
) &
PID_D=$!

log "pids harbor=$PID_H deep=$PID_D"
wait "$PID_H" "$PID_D"
log "=== PARALLEL DONE tier=${TIER} ==="
