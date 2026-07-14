#!/usr/bin/env bash
# Run on A100 pod: promote GPU, harbor+deep release, GEBCO, inventory.
set -euo pipefail
REPO=/workspace/Charybdis
cd "$REPO"
source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export MPLBACKEND=Agg
LOG=/tmp/pod_a100_finish.log
: >"$LOG"
ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

if [[ -f models/tcm_so2_best_lane0.pt ]]; then
  cp models/tcm_so2_best_lane0.pt models/tcm_so2.pt
  cp models/tcm_so2_best_lane0.pt models/tcm_so2_best.pt
  log "promoted tcm_so2_best_lane0.pt -> tcm_so2.pt"
fi

STAMP=$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD 2>/dev/null || echo synced)
ROOT_OUT="artifacts/validation/${STAMP}"
mkdir -p "${ROOT_OUT}"
python -m pip freeze > "${ROOT_OUT}/requirements-freeze.txt"
log "ROOT_OUT=${ROOT_OUT}"

H_OUT="${ROOT_OUT}/release"
D_OUT="${ROOT_OUT}/deep_release"
log "=== harbor+deep release 256 (parallel) ==="
(
  python scripts/hybrid_validate_matrix.py \
    --tier release --runs 256 --workers 31 --allow-dirty \
    --output-dir "$H_OUT" 2>&1 | tee /tmp/pod_harbor_release.log
  echo "HARBOR_RELEASE_DONE" >>/tmp/pod_harbor_release.log
) &
PID_H=$!
(
  python scripts/hybrid_validate_deep_matrix.py \
    --tier release --runs 256 --workers 31 --allow-dirty \
    --output-dir "$D_OUT" 2>&1 | tee /tmp/pod_deep_release.log
  echo "DEEP_RELEASE_DONE" >>/tmp/pod_deep_release.log
) &
PID_D=$!
wait "$PID_H" "$PID_D"
log "release matrices done"

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
