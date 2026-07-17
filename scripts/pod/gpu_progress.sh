#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
for g in 0 1; do
  echo "=== gpu${g} ==="
  grep -E 'PASS |after_mean|new_best|FINAL|train_wall' /tmp/pod_gpu_lane${g}.log 2>/dev/null | tail -6 || tail -4 /tmp/pod_gpu_lane${g}.log 2>/dev/null || echo idle
done
nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader
REMOTE
