#!/usr/bin/env bash
# 4 CPU clusters on 112 vCPU: taskset 0-27 / 28-55 / 56-83 / 84-111 @ 28 workers each.
# One validation job per cluster; round-robin queue feeds free slots. TRUE PARALLEL.
set -euo pipefail

REPO=/workspace/Charybdis
LOG=/tmp/pod_quad_cluster.log
: >"$LOG"

ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

cd "$REPO"
source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 MPLBACKEND=Agg

WORKERS="${CLUSTER_WORKERS:-28}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD 2>/dev/null || echo synced)"
OUT="artifacts/validation/${STAMP}/quad_cluster"
mkdir -p "$OUT"

HARBOR_WORST=(sparse_outlier_bathymetry repeated_mode_transitions)
DEEP_WORST=(deep_midwater deep_long_blackout deep_sparse_bathymetry)

log "QUAD_CLUSTER_START cpus=$(nproc) workers=${WORKERS} OUT=${OUT}"

done_if() {
  local marker="$1"
  [[ -f "${OUT}/.done/${marker}" ]]
}

mark_done() {
  mkdir -p "${OUT}/.done"
  touch "${OUT}/.done/$1"
}

skip_if_done() {
  local marker="$1"
  if done_if "$marker"; then
    log "skip ${marker} (already done this run)"
    return 0
  fi
  return 1
}

# Build job queue (name|command) — skip if output already exists from earlier today
QUEUE=()

add_job() {
  local name="$1"
  shift
  if done_if "$name"; then
    return 0
  fi
  QUEUE+=("${name}|$*")
}

add_job harbor_eng python scripts/hybrid_validate_matrix.py \
  --tier engineering --runs 64 --workers "${WORKERS}" --allow-dirty \
  --output-dir "${OUT}/harbor_engineering"

add_job harbor_rel python scripts/hybrid_validate_matrix.py \
  --tier release --runs 256 --workers "${WORKERS}" --allow-dirty \
  --output-dir "${OUT}/harbor_release"

add_job deep_eng python scripts/hybrid_validate_deep_matrix.py \
  --tier engineering --runs 64 --workers "${WORKERS}" --allow-dirty \
  --output-dir "${OUT}/deep_engineering"

add_job deep_rel python scripts/hybrid_validate_deep_matrix.py \
  --tier release --runs 256 --workers "${WORKERS}" --allow-dirty \
  --output-dir "${OUT}/deep_release"

add_job mission256 python scripts/hybrid_validate_mission_matrix.py \
  --tier engineering --runs 256 --workers "${WORKERS}" --allow-dirty \
  --output-dir "${OUT}/mission_engineering"

add_job harbor_worst_eng python scripts/hybrid_validate_matrix.py \
  --tier engineering --runs 512 --workers "${WORKERS}" --allow-dirty \
  --scenarios "${HARBOR_WORST[@]}" \
  --output-dir "${OUT}/harbor_worst_engineering"

add_job harbor_worst_rel python scripts/hybrid_validate_matrix.py \
  --tier release --runs 512 --workers "${WORKERS}" --allow-dirty \
  --scenarios "${HARBOR_WORST[@]}" \
  --output-dir "${OUT}/harbor_worst_release"

add_job deep_worst_eng python scripts/hybrid_validate_deep_matrix.py \
  --tier engineering --runs 512 --workers "${WORKERS}" --allow-dirty \
  --scenarios "${DEEP_WORST[@]}" \
  --output-dir "${OUT}/deep_worst_engineering"

add_job deep_worst_rel python scripts/hybrid_validate_deep_matrix.py \
  --tier release --runs 512 --workers "${WORKERS}" --allow-dirty \
  --scenarios "${DEEP_WORST[@]}" \
  --output-dir "${OUT}/deep_worst_release"

add_job highres bash scripts/pod/pod_highres_bathy.sh

add_job gebco bash -c "
  set -euo pipefail
  cd ${REPO} && source .venv/bin/activate
  mkdir -p ${OUT}/real_bathymetry
  python scripts/prepare_gebco_tile.py \
    --output ${OUT}/real_bathymetry/gebco_monterey.npz \
    --download ${OUT}/real_bathymetry/gebco_subset.nc
  python scripts/real_bathymetry_validate.py --tile ${OUT}/real_bathymetry/gebco_monterey.npz \
    --tier engineering --runs 64 --workers ${WORKERS} --seeds validation/seeds_v1.txt \
    --output ${OUT}/real_bathymetry/engineering.json
  python scripts/real_bathymetry_validate.py --tile ${OUT}/real_bathymetry/gebco_monterey.npz \
    --tier release --runs 256 --workers ${WORKERS} --seeds validation/seeds_v1.txt \
    --output ${OUT}/real_bathymetry/release.json
"

add_job legacy bash -c "
  set -euo pipefail
  cd ${REPO} && source .venv/bin/activate
  python scripts/stress_run.py 64 | tee ${OUT}/legacy_stress.log
"

log "queue_size=${#QUEUE[@]}"

# Round-robin split into 4 cluster queues
Q0=() Q1=() Q2=() Q3=()
for i in "${!QUEUE[@]}"; do
  case $((i % 4)) in
    0) Q0+=("${QUEUE[$i]}") ;;
    1) Q1+=("${QUEUE[$i]}") ;;
    2) Q2+=("${QUEUE[$i]}") ;;
    3) Q3+=("${QUEUE[$i]}") ;;
  esac
done

run_cluster() {
  local cid="$1"
  local cpus="$2"
  shift 2
  local jobs=("$@")
  local clog="/tmp/cluster${cid}.log"
  : >"$clog"
  log "cluster${cid} START cpus=${cpus} jobs=${#jobs[@]}"
  for entry in "${jobs[@]}"; do
    local name="${entry%%|*}"
    local cmd="${entry#*|}"
    if done_if "$name"; then
      echo "[cluster${cid}] skip ${name}" >>"$clog"
      continue
    fi
    echo "[cluster${cid}] RUN ${name} $(date -u +%H:%M:%SZ)" >>"$clog"
    if taskset -c "$cpus" bash -c "cd ${REPO} && source .venv/bin/activate && export PYTHONPATH=. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 MPLBACKEND=Agg && ${cmd}" >>"$clog" 2>&1; then
      mark_done "$name"
      echo "[cluster${cid}] DONE ${name} $(date -u +%H:%M:%SZ)" >>"$clog"
    else
      echo "[cluster${cid}] FAIL ${name} $(date -u +%H:%M:%SZ)" >>"$clog"
    fi
  done
  log "cluster${cid} COMPLETE"
}

run_cluster 0 "0-27" "${Q0[@]}" &
pid0=$!
run_cluster 1 "28-55" "${Q1[@]}" &
pid1=$!
run_cluster 2 "56-83" "${Q2[@]}" &
pid2=$!
run_cluster 3 "84-111" "${Q3[@]}" &
pid3=$!

log "cluster pids: 0=$pid0 1=$pid1 2=$pid2 3=$pid3"

wait "$pid0" "$pid1" "$pid2" "$pid3"

(
  cd "${OUT}"
  find . -type f \( -name '*.json' -o -name '*.md' -o -name '*.log' \) -print0 2>/dev/null \
    | xargs -0 sha256sum > SHA256SUMS 2>/dev/null || true
)

log "QUAD_CLUSTER_COMPLETE out=${OUT}"
