#!/usr/bin/env bash
# Follow-on CPU work after worst_sweep: real bathy + integration rerun.
set -euo pipefail
REPO=/workspace/Charybdis
cd "$REPO"
LOG=/tmp/pod_cpu_followon.log
: >"$LOG"
ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

log "FOLLOWON_START waiting for worst_sweep"
while pgrep -f pod_worst_sweep >/dev/null 2>&1; do sleep 15; done
log "worst_sweep done"

source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

TILE=$(ls -t artifacts/validation/*/real_bathymetry/gebco_monterey.npz 2>/dev/null | head -1 || true)
if [[ -n "${TILE}" && -f "${TILE}" ]]; then
  STAMP=$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD 2>/dev/null || echo synced)
  RB_OUT="artifacts/validation/${STAMP}/real_bathymetry_rerun"
  mkdir -p "${RB_OUT}"
  log "real_bathy engineering tile=${TILE}"
  python scripts/real_bathymetry_validate.py --tile "${TILE}" --tier engineering --runs 256 --workers 31 --output "${RB_OUT}/engineering.json" 2>&1 | tee -a "$LOG"
  log "real_bathy release"
  python scripts/real_bathymetry_validate.py --tile "${TILE}" --tier release --runs 256 --workers 31 --output "${RB_OUT}/release.json" 2>&1 | tee -a "$LOG"
else
  log "skip real_bathy no tile; fetching gebco"
  STAMP=$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD 2>/dev/null || echo synced)
  RB_OUT="artifacts/validation/${STAMP}/real_bathymetry_fetch"
  mkdir -p "${RB_OUT}/real_bathymetry"
  python scripts/prepare_gebco_tile.py \
    --output "${RB_OUT}/real_bathymetry/gebco_monterey.npz" \
    --download "${RB_OUT}/real_bathymetry/gebco_subset.nc" 2>&1 | tee -a "$LOG" || log "gebco fetch failed"
  TILE="${RB_OUT}/real_bathymetry/gebco_monterey.npz"
  if [[ -f "${TILE}" ]]; then
    python scripts/real_bathymetry_validate.py --tile "${TILE}" --tier engineering --runs 256 --workers 31 --output "${RB_OUT}/engineering.json" 2>&1 | tee -a "$LOG"
    python scripts/real_bathymetry_validate.py --tile "${TILE}" --tier release --runs 256 --workers 31 --output "${RB_OUT}/release.json" 2>&1 | tee -a "$LOG"
  fi
fi

log "integration_grade rerun"
bash scripts/pod/pod_integration_grade.sh 2>&1 | tee -a "$LOG"
log "FOLLOWON_COMPLETE"
