#!/usr/bin/env bash
set -euo pipefail

REPO=/workspace/Charybdis
LOG=/tmp/pod_phase2.log

ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

mkdir -p /workspace
cd /workspace
: >"$LOG"

if [[ -d Charybdis/.git ]]; then
  log "update existing repo"
  cd Charybdis
  git fetch --all -q
  git checkout main -q
  git pull -q
else
  log "clone Charybdis"
  git clone -q https://github.com/Fratres-X-AI/Charybdis.git
  cd Charybdis
fi

SHA="$(git rev-parse --short HEAD)"
log "HEAD ${SHA}"

if [[ ! -d .venv ]]; then
  log "create venv"
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install -q -U pip
log "install ci deps"
python -m pip install -q -c requirements/ci.txt -e ".[dev]"

for f in scripts/pod/pod_hybrid_phase2.sh scripts/pod/phase1_pod.sh; do
  sed -i 's/\r$//' "$f"
  chmod +x "$f"
done

log "start Phase 2 hybrid validation"
VALIDATION_WORKERS=31 \
ENGINEERING_RUNS=64 \
RELEASE_RUNS=256 \
LEGACY_STRESS_RUNS=64 \
SEEDS_FILE=validation/seeds_v1.txt \
bash scripts/pod/pod_hybrid_phase2.sh 2>&1 | tee -a "$LOG"

log "Phase 2 complete"
