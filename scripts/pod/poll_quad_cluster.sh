#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
echo "=== $(date -u +%H:%M:%SZ) QUAD CLUSTER ==="
echo "load=$(cat /proc/loadavg) cpus=$(nproc)"
echo "validate=$(pgrep -c -f hybrid_validate 2>/dev/null || echo 0)"
echo "gpu_lanes=$(pgrep -c -f pod_max_gpu_lane 2>/dev/null || echo 0)"
for c in 0 1 2 3; do
  echo "--- cluster${c} tail ---"
  tail -3 /tmp/cluster${c}.log 2>/dev/null || echo "(idle)"
done
grep -E 'QUAD_CLUSTER|cluster[0-3]' /tmp/pod_quad_cluster.log 2>/dev/null | tail -10 || true
ls -1dt artifacts/validation/*/quad_cluster 2>/dev/null | head -1 || true
nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader 2>/dev/null || true
REMOTE
