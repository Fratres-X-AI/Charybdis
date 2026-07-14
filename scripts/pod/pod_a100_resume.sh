#!/usr/bin/env bash
# Resume A100 Phase 2 from GEBCO (release matrices already done).
set -euo pipefail
REPO=/workspace/Charybdis
cd "$REPO"
source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export MPLBACKEND=Agg
LOG=/tmp/pod_a100_finish.log
ROOT_OUT="${1:-artifacts/validation/20260714T132210Z-ad7fa3e}"
ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

log "RESUME ROOT_OUT=${ROOT_OUT}"

if [[ ! -f "${ROOT_OUT}/release/matrix_summary.json" ]]; then
  log "ERROR missing harbor release artifacts"
  exit 1
fi
if [[ ! -f "${ROOT_OUT}/deep_release/matrix_summary.json" ]]; then
  log "ERROR missing deep release artifacts"
  exit 1
fi

log "=== GEBCO tile + real bathymetry ==="
python scripts/prepare_gebco_tile.py \
  --output "${ROOT_OUT}/real_bathymetry/gebco_monterey.npz" \
  --download "${ROOT_OUT}/real_bathymetry/gebco_subset.nc" 2>&1 | tee -a "$LOG"

python scripts/real_bathymetry_validate.py \
  --tile "${ROOT_OUT}/real_bathymetry/gebco_monterey.npz" \
  --tier engineering --runs 64 --workers 31 \
  --seeds validation/seeds_v1.txt \
  --output "${ROOT_OUT}/real_bathymetry/engineering.json" 2>&1 | tee -a "$LOG"

python scripts/real_bathymetry_validate.py \
  --tile "${ROOT_OUT}/real_bathymetry/gebco_monterey.npz" \
  --tier release --runs 256 --workers 31 \
  --seeds validation/seeds_v1.txt \
  --output "${ROOT_OUT}/real_bathymetry/release.json" 2>&1 | tee -a "$LOG"

log "=== legacy stress ==="
python scripts/stress_run.py 64 | tee "${ROOT_OUT}/legacy_stress.log"

log "=== SHA256 inventory ==="
(
  cd "${ROOT_OUT}"
  sha256sum \
    requirements-freeze.txt \
    release/*.json release/REPORT.md \
    deep_release/*.json deep_release/REPORT.md \
    real_bathymetry/*.json real_bathymetry/*.md \
    real_bathymetry/*.npz real_bathymetry/*.nc \
    legacy_stress.log > SHA256SUMS
)
log "A100_PHASE2_COMPLETE ${ROOT_OUT}"
