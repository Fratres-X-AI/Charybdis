#!/usr/bin/env bash
# Full military-grade Phase 2: eng + release harbor/deep, GEBCO, stress, SHA256.
set -euo pipefail
REPO=/workspace/Charybdis
cd "$REPO"
LOG=/tmp/pod_bronze_military.log
: >"$LOG"
ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

if [[ ! -d .venv ]]; then
  log "bootstrap venv"
  python3 -m venv .venv
  source .venv/bin/activate
  python -m pip install -q -U pip setuptools wheel
  python -m pip install -q -c requirements/ci.txt -e ".[dev]"
  python -m pip install -q torch --index-url https://download.pytorch.org/whl/cu126
else
  source .venv/bin/activate
fi
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export MPLBACKEND=Agg

STAMP=$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD 2>/dev/null || echo synced)
ROOT_OUT="artifacts/validation/${STAMP}"
mkdir -p "${ROOT_OUT}"
python -m pip freeze > "${ROOT_OUT}/requirements-freeze.txt"
log "ROOT_OUT=${ROOT_OUT} cpus=$(nproc)"

run_dual() {
  local tier="$1"
  local runs="$2"
  local h_out="${ROOT_OUT}/engineering"
  local d_out="${ROOT_OUT}/deep_engineering"
  if [[ "$tier" == "release" ]]; then
    h_out="${ROOT_OUT}/release"
    d_out="${ROOT_OUT}/deep_release"
  fi
  log "=== ${tier} ${runs} harbor+deep (31+31 workers) ==="
  (
    python scripts/hybrid_validate_matrix.py \
      --tier "$tier" --runs "$runs" --workers 31 --allow-dirty \
      --output-dir "$h_out" 2>&1 | tee "/tmp/pod_harbor_${tier}.log"
  ) &
  local pid_h=$!
  (
    python scripts/hybrid_validate_deep_matrix.py \
      --tier "$tier" --runs "$runs" --workers 31 --allow-dirty \
      --output-dir "$d_out" 2>&1 | tee "/tmp/pod_deep_${tier}.log"
  ) &
  local pid_d=$!
  wait "$pid_h" "$pid_d"
}

run_dual engineering 64
run_dual release 256

log "=== GEBCO + real bathymetry ==="
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

log "=== legacy stress 64 ==="
python scripts/stress_run.py 64 | tee "${ROOT_OUT}/legacy_stress.log"

log "=== SHA256 inventory ==="
(
  cd "${ROOT_OUT}"
  sha256sum \
    requirements-freeze.txt \
    engineering/*.json engineering/REPORT.md \
    deep_engineering/*.json deep_engineering/REPORT.md \
    release/*.json release/REPORT.md \
    deep_release/*.json deep_release/REPORT.md \
    real_bathymetry/*.json real_bathymetry/*.md \
    real_bathymetry/*.npz real_bathymetry/*.nc \
    legacy_stress.log > SHA256SUMS
)
log "BRONZE_MILITARY_COMPLETE ${ROOT_OUT}"
