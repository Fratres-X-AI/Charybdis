#!/usr/bin/env bash
# Close out Phase 2: legacy stress + SHA256 only.
set -euo pipefail
ROOT_OUT="${1:-artifacts/validation/20260714T132210Z-ad7fa3e}"
cd /workspace/Charybdis
source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
LOG=/tmp/pod_a100_finish.log
ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

if [[ ! -f "${ROOT_OUT}/legacy_stress.log" ]] || [[ ! -s "${ROOT_OUT}/legacy_stress.log" ]]; then
  log "=== legacy stress ==="
  python scripts/stress_run.py 64 | tee "${ROOT_OUT}/legacy_stress.log"
else
  log "skip stress (log exists)"
fi

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
