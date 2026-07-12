#!/usr/bin/env bash
# Full dual-pod pipeline: Phase1 -> dual CPU matrices -> dual GPU max.
set -euo pipefail

REPO=/workspace/Charybdis
LOG=/tmp/pod_dual_full.log

ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

: >"$LOG"
cd "$REPO"
log "dual full sprint cpus=$(nproc) gpus=$(nvidia-smi -L 2>/dev/null | wc -l)"
log "HEAD $(git rev-parse --short HEAD 2>/dev/null || echo synced)"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install -q -U pip
python -m pip install -q -c requirements/ci.txt -e ".[dev]"

log "=== PHASE 1 ==="
bash scripts/pod/phase1_pod.sh 2>&1 | tee -a "$LOG"
log "PHASE1_DONE"

log "=== PHASE 2 engineering (31+31 NUMA) ==="
bash scripts/pod/pod_dual_matrix.sh engineering 64 2>&1 | tee -a "$LOG"
log "PHASE2_ENG_DONE"

log "=== PHASE 2 release (31+31 NUMA) ==="
bash scripts/pod/pod_dual_matrix.sh release 256 2>&1 | tee -a "$LOG"
log "PHASE2_REL_DONE"

log "=== PHASE 3 dual GPU max (4090 x2) ==="
bash scripts/pod/pod_dual_gpu_max.sh 2>&1 | tee -a "$LOG"
log "PHASE3_GPU_DONE"

log "=== DUAL FULL COMPLETE ==="
