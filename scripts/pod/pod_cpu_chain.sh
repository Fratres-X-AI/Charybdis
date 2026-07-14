#!/usr/bin/env bash
# Chain release grade -> worst-scenario 512 sweep without idle gap.
set -euo pipefail
REPO=/workspace/Charybdis
cd "$REPO"
LOG=/tmp/pod_cpu_chain.log
: >"$LOG"
ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

log "CHAIN_START waiting for release_grade if running"
while pgrep -f pod_release_grade >/dev/null 2>&1; do
  sleep 15
done
log "release done or absent; starting worst_sweep"
bash scripts/pod/pod_worst_sweep.sh 2>&1 | tee -a "$LOG"
log "worst_sweep done; starting real_bathy if tile present"
TILE=$(ls -t artifacts/validation/*/real_bathymetry/gebco_monterey.npz 2>/dev/null | head -1 || true)
if [[ -n "${TILE}" && -f "${TILE}" ]]; then
  STAMP=$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD 2>/dev/null || echo synced)
  RB_OUT="artifacts/validation/${STAMP}/real_bathymetry_rerun"
  mkdir -p "${RB_OUT}"
  python scripts/real_bathymetry_validate.py --tile "${TILE}" --tier engineering --runs 256 --workers 31 --output "${RB_OUT}/engineering.json" 2>&1 | tee -a "$LOG"
  python scripts/real_bathymetry_validate.py --tile "${TILE}" --tier release --runs 256 --workers 31 --output "${RB_OUT}/release.json" 2>&1 | tee -a "$LOG"
  log "real_bathy done ${RB_OUT}"
else
  log "skip real_bathy (no gebco tile on pod)"
fi
log "starting integration_grade rerun"
bash scripts/pod/pod_integration_grade.sh 2>&1 | tee -a "$LOG"
log "CHAIN_COMPLETE"
