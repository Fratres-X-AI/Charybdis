#!/usr/bin/env bash
# Poll every 90s, incremental artifact pull, until elite pass completes.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
PULL_DEST="$LOCAL_ROOT/artifacts/pod_elite_pull_${STAMP}"
INTERVAL="${ELITE_POLL_SEC:-90}"
MAX_HOURS="${ELITE_MAX_HOURS:-12}"
MAX_LOOPS=$((MAX_HOURS * 3600 / INTERVAL))

echo "=== BABYSIT elite phase34 pod=${POD_NAME} interval=${INTERVAL}s max_hours=${MAX_HOURS} ==="
echo "pull_dest=$PULL_DEST"

loop=0
while (( loop < MAX_LOOPS )); do
  loop=$((loop + 1))
  echo ""
  echo "========== loop $loop $(date -u +%H:%M:%SZ) =========="
  bash "$SCRIPT_DIR/poll_elite_phase34.sh" || true
  bash "$SCRIPT_DIR/pull_incremental.sh" "$STAMP" || true

  if ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
    'grep -q ELITE_PHASE34_COMPLETE /tmp/pod_elite_phase34.log 2>/dev/null'; then
    echo "=== ELITE_PHASE34_COMPLETE detected — final pull ==="
    bash "$SCRIPT_DIR/pull_incremental.sh" "$STAMP" || true
    # Pull models if GPU lane finished
    scp -o StrictHostKeyChecking=no -P "$POD_PORT" -i "$POD_KEY" -r \
      "$POD_HOST:/workspace/Charybdis/models/" "$PULL_DEST/" 2>/dev/null || true
    echo "BABYSIT_DONE dest=$PULL_DEST"
    exit 0
  fi

  sleep "$INTERVAL"
done

echo "BABYSIT_TIMEOUT after ${MAX_HOURS}h — last incremental pull"
bash "$SCRIPT_DIR/pull_incremental.sh" "$STAMP" || true
exit 1
