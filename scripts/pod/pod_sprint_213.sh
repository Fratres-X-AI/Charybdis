#!/usr/bin/env bash
# Sprint validation: Phase 1 acceptance then Phase 2 matrix on synced private-repo tree.
set -euo pipefail

REPO=/workspace/Charybdis
LOG=/tmp/pod_sprint.log

ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

: >"$LOG"
cd "$REPO"
log "sprint HEAD $(git rev-parse --short HEAD 2>/dev/null || echo synced-tree)"

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

log "=== PHASE 2 hybrid validation ==="
VALIDATION_WORKERS=31 \
ENGINEERING_RUNS=64 \
RELEASE_RUNS=256 \
LEGACY_STRESS_RUNS=64 \
SEEDS_FILE=validation/seeds_v1.txt \
bash scripts/pod/pod_hybrid_phase2.sh 2>&1 | tee -a "$LOG"

log "=== SPRINT COMPLETE ==="
