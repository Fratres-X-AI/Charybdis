#!/usr/bin/env bash
source "$(cd "$(dirname "$0")" && pwd)/pod_env.sh"
ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set +e
nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader
echo "--- procs ---"
pgrep -af 'python|bash scripts/pod' | grep -v grep | head -25
echo "--- full_pass ---"
tail -10 /tmp/pod_post_train_full_pass.log 2>/dev/null || echo none
echo "--- followon ---"
tail -6 /tmp/pod_h200_followon.log 2>/dev/null || echo none
REMOTE
