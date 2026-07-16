#!/usr/bin/env bash
# 90s poll + incremental pull until quad cluster (phase 3+4) completes. Git Bash only.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
PULL_DEST="$LOCAL_ROOT/artifacts/pod_quad_pull_${STAMP}"
INTERVAL="${ELITE_POLL_SEC:-90}"
MAX_HOURS="${ELITE_MAX_HOURS:-14}"
MAX_LOOPS=$((MAX_HOURS * 3600 / INTERVAL))

echo "=== BABYSIT quad cluster pod=${POD_NAME} interval=${INTERVAL}s ==="
echo "pull_dest=$PULL_DEST"

loop=0
while (( loop < MAX_LOOPS )); do
  loop=$((loop + 1))
  echo ""
  echo "========== loop $loop $(date -u +%H:%M:%SZ) =========="
  bash "$SCRIPT_DIR/poll_quad_cluster.sh" || true
  bash "$SCRIPT_DIR/pull_incremental.sh" "$STAMP" || true

  if ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
    'grep -q QUAD_CLUSTER_COMPLETE /tmp/pod_quad_cluster.log 2>/dev/null'; then
    echo "=== QUAD_CLUSTER_COMPLETE — final pull ==="
    bash "$SCRIPT_DIR/pull_incremental.sh" "$STAMP" || true
    scp -o StrictHostKeyChecking=no -P "$POD_PORT" -i "$POD_KEY" -r \
      "$POD_HOST:/workspace/Charybdis/models/" "$PULL_DEST/" 2>/dev/null || true
    scp -o StrictHostKeyChecking=no -P "$POD_PORT" -i "$POD_KEY" \
      "$POD_HOST:/tmp/cluster0.log" "$POD_HOST:/tmp/cluster1.log" \
      "$POD_HOST:/tmp/cluster2.log" "$POD_HOST:/tmp/cluster3.log" \
      "$POD_HOST:/tmp/pod_quad_cluster.log" "$POD_HOST:/tmp/pod_quad_cluster_stdout.log" \
      "$PULL_DEST/logs/" 2>/dev/null || true
    echo "BABYSIT_DONE dest=$PULL_DEST"
    exit 0
  fi

  sleep "$INTERVAL"
done

echo "BABYSIT_TIMEOUT — last pull"
bash "$SCRIPT_DIR/pull_incremental.sh" "$STAMP" || true
exit 1
