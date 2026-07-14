#!/usr/bin/env bash
set -euo pipefail
REPO=/workspace/Charybdis
cd "$REPO"
LOG=/tmp/pod_gebco_job.log
: >"$LOG"
ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

STAMP=$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD 2>/dev/null || echo synced)
OUT="artifacts/validation/${STAMP}/real_bathymetry_job"
mkdir -p "${OUT}/real_bathymetry"

log "prepare gebco tile"
python scripts/prepare_gebco_tile.py \
  --output "${OUT}/real_bathymetry/gebco_monterey.npz" \
  --download "${OUT}/real_bathymetry/gebco_subset.nc" 2>&1 | tee -a "$LOG"

TILE="${OUT}/real_bathymetry/gebco_monterey.npz"
log "engineering real_bathymetry validate"
python scripts/real_bathymetry_validate.py \
  --tile "${TILE}" --tier engineering --runs 256 --workers 31 \
  --output "${OUT}/engineering.json" 2>&1 | tee -a "$LOG"

log "release real_bathymetry validate"
python scripts/real_bathymetry_validate.py \
  --tile "${TILE}" --tier release --runs 256 --workers 31 \
  --output "${OUT}/release.json" 2>&1 | tee -a "$LOG"

python3 -c "import json; e=json.load(open('${OUT}/engineering.json')); r=json.load(open('${OUT}/release.json')); print('GEBCO_JOB eng_pass',e['results']['passed'],'rel_pass',r['results']['passed'])" | tee -a "$LOG"
log "GEBCO_JOB_COMPLETE ${OUT}"
