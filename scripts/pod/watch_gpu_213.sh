#!/usr/bin/env bash
set -euo pipefail
HOST=root@213.192.2.94
PORT=40077
KEY="${HOME}/.ssh/id_ed25519"
ssh -p "$PORT" -i "$KEY" "$HOST" <<'REMOTE'
echo "=== $(date -u +%H:%M:%S) UTC ==="
pgrep -af 'pod_max_gpu|ten_pass|nn_matcher|train\(' || echo "no_train_proc"
nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu,power.draw --format=csv,noheader 2>/dev/null || nvidia-smi | tail -n 15
echo "--- log tail ---"
tail -n 12 /tmp/pod_max_gpu.log 2>/dev/null || tail -n 12 /tmp/pod_max_gpu.out 2>/dev/null || true
REMOTE
