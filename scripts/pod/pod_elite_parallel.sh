#!/usr/bin/env bash
# TRUE FLAT PARALLEL — every job is independent nohup at t=0. No sequential chains.
# 112 CPU ≈ 4×28-worker lanes (same as 4 rented pods @ 31 each).
set -euo pipefail

REPO=/workspace/Charybdis
LOG=/tmp/pod_elite_parallel.log
: >"$LOG"

ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

cd "$REPO"
source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 MPLBACKEND=Agg

WORKERS="${VALIDATION_WORKERS:-28}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD 2>/dev/null || echo synced)"
OUT="artifacts/validation/${STAMP}/elite_parallel"
mkdir -p "$OUT"
python -m pip freeze > "${OUT}/requirements-freeze.txt"

HARBOR_WORST=(sparse_outlier_bathymetry repeated_mode_transitions)
DEEP_WORST=(deep_midwater deep_long_blackout deep_sparse_bathymetry)

log "ELITE_PARALLEL_START cpus=$(nproc) workers=${WORKERS} gpus=$(nvidia-smi -L 2>/dev/null | wc -l) HEAD=$(git rev-parse --short HEAD 2>/dev/null || echo synced)"

launch() {
  local name="$1"
  shift
  log "launch ${name}"
  nohup "$@" >"/tmp/pod_par_${name}.log" 2>&1 &
  echo "$!" >>"${OUT}/pids.txt"
}

# --- Harbor synthetic (all tiers at once, separate output dirs) ---
launch harbor_eng python scripts/hybrid_validate_matrix.py \
  --tier engineering --runs 64 --workers "${WORKERS}" --allow-dirty \
  --output-dir "${OUT}/harbor_engineering"

launch harbor_rel python scripts/hybrid_validate_matrix.py \
  --tier release --runs 256 --workers "${WORKERS}" --allow-dirty \
  --output-dir "${OUT}/harbor_release"

launch harbor_worst_eng python scripts/hybrid_validate_matrix.py \
  --tier engineering --runs 512 --workers "${WORKERS}" --allow-dirty \
  --scenarios "${HARBOR_WORST[@]}" \
  --output-dir "${OUT}/harbor_worst_engineering"

launch harbor_worst_rel python scripts/hybrid_validate_matrix.py \
  --tier release --runs 512 --workers "${WORKERS}" --allow-dirty \
  --scenarios "${HARBOR_WORST[@]}" \
  --output-dir "${OUT}/harbor_worst_release"

# --- Deep synthetic (all tiers at once) ---
launch deep_eng python scripts/hybrid_validate_deep_matrix.py \
  --tier engineering --runs 64 --workers "${WORKERS}" --allow-dirty \
  --output-dir "${OUT}/deep_engineering"

launch deep_rel python scripts/hybrid_validate_deep_matrix.py \
  --tier release --runs 256 --workers "${WORKERS}" --allow-dirty \
  --output-dir "${OUT}/deep_release"

launch deep_worst_eng python scripts/hybrid_validate_deep_matrix.py \
  --tier engineering --runs 512 --workers "${WORKERS}" --allow-dirty \
  --scenarios "${DEEP_WORST[@]}" \
  --output-dir "${OUT}/deep_worst_engineering"

launch deep_worst_rel python scripts/hybrid_validate_deep_matrix.py \
  --tier release --runs 512 --workers "${WORKERS}" --allow-dirty \
  --scenarios "${DEEP_WORST[@]}" \
  --output-dir "${OUT}/deep_worst_release"

# --- Mission + highres + GEBCO + legacy (each independent) ---
launch mission256 python scripts/hybrid_validate_mission_matrix.py \
  --tier engineering --runs 256 --workers "${WORKERS}" --allow-dirty \
  --output-dir "${OUT}/mission_engineering"

launch highres bash scripts/pod/pod_highres_bathy.sh

launch gebco_dl python scripts/prepare_gebco_tile.py \
  --output "${OUT}/real_bathymetry/gebco_monterey.npz" \
  --download "${OUT}/real_bathymetry/gebco_subset.nc"

# GEBCO validate starts after download in same nohup chain — split download first, validate launched by watcher
launch gebco_val bash -c "
  set -euo pipefail
  cd ${REPO}
  source .venv/bin/activate
  while [[ ! -f ${OUT}/real_bathymetry/gebco_monterey.npz ]]; do sleep 10; done
  python scripts/real_bathymetry_validate.py --tile ${OUT}/real_bathymetry/gebco_monterey.npz \
    --tier engineering --runs 64 --workers ${WORKERS} --seeds validation/seeds_v1.txt \
    --output ${OUT}/real_bathymetry/engineering.json
  python scripts/real_bathymetry_validate.py --tile ${OUT}/real_bathymetry/gebco_monterey.npz \
    --tier release --runs 256 --workers ${WORKERS} --seeds validation/seeds_v1.txt \
    --output ${OUT}/real_bathymetry/release.json
"

launch legacy bash -c "
  set -euo pipefail
  cd ${REPO}
  source .venv/bin/activate
  python scripts/stress_run.py 64 | tee ${OUT}/legacy_stress.log
"

# --- 4 GPU lanes (Blackwell needs cu130 torch — fixed by kick script) ---
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L 2>/dev/null | grep -q GPU; then
  for gpu in 0 1 2 3; do
    if (( gpu < $(nvidia-smi -L 2>/dev/null | wc -l) )); then
      case "$gpu" in 0) lane=a ;; 1) lane=b ;; 2) lane=c ;; 3) lane=d ;; esac
      launch "gpu${gpu}" bash scripts/pod/pod_max_gpu_lane.sh "$gpu" "$lane"
    fi
  done
fi

log "ELITE_PARALLEL_LAUNCHED out=${OUT} jobs=$(wc -l <"${OUT}/pids.txt")"
log "poll: pgrep -c hybrid_validate; nvidia-smi"

# Wait for all validation + GPU (flat wait on all child PIDs)
wait
(
  cd "${OUT}"
  find . -type f \( -name '*.json' -o -name '*.md' -o -name '*.npz' -o -name '*.log' \) -print0 2>/dev/null \
    | xargs -0 sha256sum > SHA256SUMS 2>/dev/null || true
)
log "ELITE_PARALLEL_COMPLETE stamp=${STAMP}"
