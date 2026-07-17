#!/usr/bin/env bash
# Saturate CPU while GPU lanes train. Does NOT touch GPUs.
set -euo pipefail

REPO=/workspace/Charybdis
LOG=/tmp/pod_cpu_elite.log
: >"$LOG"

ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

cd "$REPO"
if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 MPLBACKEND=Agg

WORKERS="${CPU_ELITE_WORKERS:-16}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD 2>/dev/null || echo synced)"
OUT="artifacts/validation/${STAMP}/cpu_elite"
mkdir -p "$OUT"

log "CPU_ELITE_START cpus=$(nproc) workers=${WORKERS} out=${OUT}"

launch() {
  local name="$1"
  shift
  log "launch ${name}"
  nohup "$@" >"/tmp/pod_cpu_${name}.log" 2>&1 &
  echo "$!" >>"${OUT}/pids.txt"
}

launch mission python scripts/hybrid_validate_mission_matrix.py \
  --tier engineering --runs 256 --workers "${WORKERS}" --allow-dirty \
  --output-dir "${OUT}/mission_engineering"

launch holdout_h python scripts/hybrid_validate_matrix.py \
  --tier release --runs 256 --workers "${WORKERS}" --allow-dirty \
  --seeds validation/seeds_holdout_v1.txt \
  --output-dir "${OUT}/holdout_harbor"

launch holdout_d python scripts/hybrid_validate_deep_matrix.py \
  --tier release --runs 256 --workers "${WORKERS}" --allow-dirty \
  --seeds validation/seeds_holdout_v1.txt \
  --output-dir "${OUT}/holdout_deep"

launch harbor_rel python scripts/hybrid_validate_matrix.py \
  --tier release --runs 256 --workers "${WORKERS}" --allow-dirty \
  --output-dir "${OUT}/harbor_release"

launch deep_rel python scripts/hybrid_validate_deep_matrix.py \
  --tier release --runs 256 --workers "${WORKERS}" --allow-dirty \
  --output-dir "${OUT}/deep_release"

launch highres bash scripts/pod/pod_highres_bathy.sh

log "CPU_ELITE_LAUNCHED jobs=$(wc -l <"${OUT}/pids.txt")"
wait
(
  cd "${OUT}"
  find . -type f \( -name '*.json' -o -name '*.md' \) -print0 2>/dev/null \
    | xargs -0 sha256sum > SHA256SUMS 2>/dev/null || true
)
log "CPU_ELITE_COMPLETE stamp=${STAMP}"
