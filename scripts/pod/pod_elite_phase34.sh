#!/usr/bin/env bash
# Phase 3 + 4 concurrent saturation — one pod, no idle time between suites.
set -euo pipefail

REPO=/workspace/Charybdis
LOG=/tmp/pod_elite_phase34.log
: >"$LOG"

ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

cd "$REPO"
log "ELITE_PHASE34_START pod=${POD_NAME:-unknown} cpus=$(nproc) gpus=$(nvidia-smi -L 2>/dev/null | wc -l)"
log "HEAD $(git rev-parse --short HEAD 2>/dev/null || echo synced)"

bash scripts/pod/pod_bootstrap_venv.sh 2>&1 | tee -a "$LOG"
source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 MPLBACKEND=Agg

STAMP="$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD 2>/dev/null || echo synced)"
OUT="artifacts/validation/${STAMP}/elite_phase34"
mkdir -p "$OUT"

HARBOR_WORST=(sparse_outlier_bathymetry repeated_mode_transitions)
DEEP_WORST=(deep_midwater deep_long_blackout deep_sparse_bathymetry)

log "=== lane1 canonical phase2 (harbor+GEBCO+legacy) ==="
(
  bash scripts/pod/pod_hybrid_phase2.sh 2>&1 | tee /tmp/pod_phase2.log
  echo "PHASE2_COMPLETE $(date -u +%H:%M:%SZ)" >>"$LOG"
) &
pid_p2=$!

log "=== lane2 deep eng64 + release256 ==="
(
  python scripts/hybrid_validate_deep_matrix.py \
    --tier engineering --runs 64 --workers 31 --allow-dirty \
    --output-dir "${OUT}/deep_engineering" 2>&1 | tee /tmp/pod_elite_deep_eng.log
  python scripts/hybrid_validate_deep_matrix.py \
    --tier release --runs 256 --workers 31 --allow-dirty \
    --output-dir "${OUT}/deep_release" 2>&1 | tee /tmp/pod_elite_deep_rel.log
  echo "DEEP_FULL_COMPLETE $(date -u +%H:%M:%SZ)" >>"$LOG"
) &
pid_deep=$!

log "=== lane3 NOAA highres eng+release ==="
(
  bash scripts/pod/pod_highres_bathy.sh 2>&1 | tee /tmp/pod_highres_bathy.log
  echo "HIGHRES_COMPLETE $(date -u +%H:%M:%SZ)" >>"$LOG"
) &
pid_hr=$!

log "=== lane4 mission vision 256-run ==="
(
  python scripts/hybrid_validate_mission_matrix.py \
    --tier engineering --runs 256 --workers 31 --allow-dirty \
    2>&1 | tee /tmp/pod_mission_matrix.log
  echo "MISSION_256_COMPLETE $(date -u +%H:%M:%SZ)" >>"$LOG"
) &
pid_mission=$!

log "=== lane5 worst 512 engineering harbor+deep ==="
(
  bash scripts/pod/pod_worst_sweep.sh 2>&1 | tee /tmp/pod_worst_sweep.log
  echo "WORST_ENG_COMPLETE $(date -u +%H:%M:%SZ)" >>"$LOG"
) &
pid_worst_eng=$!

log "=== lane6 worst 512 release harbor+deep (phase4) ==="
(
  python scripts/hybrid_validate_matrix.py \
    --tier release --runs 512 --workers 31 --allow-dirty \
    --scenarios "${HARBOR_WORST[@]}" \
    --output-dir "${OUT}/harbor_worst_release" 2>&1 | tee /tmp/pod_worst_harbor_rel.log
  python scripts/hybrid_validate_deep_matrix.py \
    --tier release --runs 512 --workers 31 --allow-dirty \
    --scenarios "${DEEP_WORST[@]}" \
    --output-dir "${OUT}/deep_worst_release" 2>&1 | tee /tmp/pod_worst_deep_rel.log
  echo "WORST_REL_COMPLETE $(date -u +%H:%M:%SZ)" >>"$LOG"
) &
pid_worst_rel=$!

log "=== lane7 integration + release grade (harbor+deep) ==="
(
  bash scripts/pod/pod_integration_grade.sh 2>&1 | tee /tmp/pod_integration_grade.log
  bash scripts/pod/pod_release_grade.sh 2>&1 | tee /tmp/pod_release_grade_stdout.log
  echo "INTEG_RELEASE_GRADE_COMPLETE $(date -u +%H:%M:%SZ)" >>"$LOG"
) &
pid_grade=$!

log "=== lane8 quad GPU max (4x RTX PRO 4500) ==="
(
  if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L 2>/dev/null | grep -q GPU; then
    bash scripts/pod/pod_quad_gpu_max.sh 2>&1 | tee /tmp/pod_quad_gpu.log
    echo "QUAD_GPU_MAX_COMPLETE $(date -u +%H:%M:%SZ)" >>"$LOG"
  else
    log "QUAD_GPU_SKIP no cuda"
  fi
) &
pid_gpu=$!

log "=== lane9 max_out burst (release+worst+highres overlap) ==="
(
  bash scripts/pod/pod_max_out.sh 2>&1 | tee /tmp/pod_max_out.log
  echo "MAX_OUT_BURST_COMPLETE $(date -u +%H:%M:%SZ)" >>"$LOG"
) &
pid_maxout=$!

log "pids phase2=$pid_p2 deep=$pid_deep highres=$pid_hr mission=$pid_mission worst_eng=$pid_worst_eng worst_rel=$pid_worst_rel grade=$pid_grade gpu=$pid_gpu maxout=$pid_maxout"

wait "$pid_p2" "$pid_deep" "$pid_hr" "$pid_mission" "$pid_worst_eng" "$pid_worst_rel" "$pid_grade" "$pid_gpu" "$pid_maxout"

(
  cd "$REPO"
  find artifacts/validation -type f \( -name 'matrix_summary.json' -o -name 'release.json' -o -name 'SHA256SUMS' \) -print0 2>/dev/null \
    | xargs -0 sha256sum 2>/dev/null || true
) > "${OUT}/elite_inventory.sha256" || true

log "ELITE_PHASE34_COMPLETE stamp=${STAMP} out=${OUT}"
