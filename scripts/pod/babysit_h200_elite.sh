#!/usr/bin/env bash
# Babysit H200 elite until 100% GREEN — heal dead workers, pull only when all gates pass.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
PULL_DEST="$LOCAL_ROOT/artifacts/pod_h200_elite_${STAMP}"
INTERVAL="${GPU_POLL_SEC:-120}"
MAX_HOURS="${GPU_MAX_HOURS:-12}"
MAX_LOOPS=$((MAX_HOURS * 3600 / INTERVAL))
HEAL_EVERY="${HEAL_EVERY_LOOPS:-3}"

REMOTE_GPU_COUNT="$(ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" 'nvidia-smi -L 2>/dev/null | wc -l' 2>/dev/null || echo 2)"
GPU_TARGET="${GPU_TARGET:-$REMOTE_GPU_COUNT}"
if ! [[ "$GPU_TARGET" =~ ^[0-9]+$ ]] || (( GPU_TARGET < 1 )); then
  GPU_TARGET=2
fi
export GPU_TARGET

echo "=== BABYSIT H200 GREEN pod=${POD_NAME} lanes=${GPU_TARGET} max_hours=${MAX_HOURS} ==="
echo "pull_dest=${PULL_DEST}"

bash "$SCRIPT_DIR/pod_heal_h200.sh" || true

loop=0
while (( loop < MAX_LOOPS )); do
  loop=$((loop + 1))
  echo ""
  echo "========== green loop $loop/$MAX_LOOPS $(date -u +%H:%M:%SZ) =========="
  bash "$SCRIPT_DIR/gpu_progress.sh" || true
  bash "$SCRIPT_DIR/pull_h200_incremental.sh" || true

  if (( loop == 1 || loop % HEAL_EVERY == 0 )); then
    bash "$SCRIPT_DIR/pod_heal_h200.sh" || true
  fi

  set +e
  bash "$SCRIPT_DIR/pod_pipeline_green.sh" --report
  green_rc=$?
  set -e
  echo "green_exit=${green_rc}"

  if (( green_rc == 0 )); then
    echo "=== 100% GREEN — final pull ==="
    AWAY_PULL_DEST="$PULL_DEST" bash "$SCRIPT_DIR/pull_h200_shutdown.sh"
    echo "H200_GREEN_BABYSIT_DONE dest=$PULL_DEST"
    exit 0
  fi

  sleep "$INTERVAL"
done

echo "H200_GREEN_BABYSIT_TIMEOUT after ${MAX_HOURS}h — partial pull"
AWAY_PULL_DEST="$LOCAL_ROOT/artifacts/pod_h200_partial_${STAMP}" bash "$SCRIPT_DIR/pull_h200_shutdown.sh" || true
exit 1
