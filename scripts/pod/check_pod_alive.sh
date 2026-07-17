#!/usr/bin/env bash
source "$(dirname "$0")/pod_env.sh"
ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
  'echo POD_OK; nvidia-smi -L 2>&1; pgrep -c -f pod_max_gpu_lane || echo 0' 2>&1 || echo POD_UNREACHABLE
