#!/usr/bin/env bash
set -euo pipefail
HOST=root@195.26.233.70
PORT=55580
KEY="${HOME}/.ssh/id_ed25519"

ssh -p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no "$HOST" <<'REMOTE'
ts() { date -u +"%H:%M:%S"; }
echo "=== $(ts) UTC A100 ==="
echo "cpus=$(nproc) python=$(pgrep -c python || echo 0)"
pgrep -af "hybrid_validate|pod_dual_matrix|pod_max_gpu_lane" || echo "no active procs"
echo "--- harbor ---"
tail -n 2 /tmp/pod_harbor_matrix.log 2>/dev/null || true
echo "--- deep ---"
tail -n 2 /tmp/pod_deep_matrix.log 2>/dev/null || true
echo "--- gpu0 ---"
tail -n 2 /tmp/pod_gpu_lane0.log 2>/dev/null || true
nvidia-smi --query-gpu=index,utilization.gpu,memory.used,power.draw --format=csv,noheader 2>/dev/null || true
uptime
REMOTE
