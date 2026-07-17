#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
# shellcheck source=scripts/pod/pod_env.sh
source scripts/pod/pod_env.sh

echo "=== local log tail ==="
tail -40 artifacts/go_h200_sxm.log 2>/dev/null || echo "no local log"

echo ""
echo "=== remote ==="
ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set +e
cd /workspace/Charybdis 2>/dev/null || { echo "no repo yet"; exit 0; }
echo "pyproject=$(test -f pyproject.toml && echo yes || echo no)"
nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader
echo "gpu_lanes=$(pgrep -c -f 'pod_max_gpu_lane.sh' 2>/dev/null || echo 0)"
echo "quad=$(pgrep -c -f 'pod_quad_gpu_max' 2>/dev/null || echo 0)"
echo "followon=$(pgrep -c -f 'pod_h200_followon' 2>/dev/null || echo 0)"
echo "cpu=$(pgrep -c -f 'hybrid_validate' 2>/dev/null || echo 0)"
echo "hotzone=$(pgrep -c -f 'pod_hotzone_bathy' 2>/dev/null || echo 0)"
pgrep -af 'pod_max_gpu_lane|pod_quad_gpu|pod_h200_followon|hybrid_validate|pod_hotzone' | head -16
echo "--- lane0 ---"
tail -3 /tmp/pod_gpu_lane0.log 2>/dev/null || echo "no lane0"
echo "--- lane1 ---"
tail -3 /tmp/pod_gpu_lane1.log 2>/dev/null || echo "no lane1"
REMOTE
