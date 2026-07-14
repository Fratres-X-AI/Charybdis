#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

echo "=== SYNC $(date -u +%H:%M:%SZ) ==="
bash "$SCRIPT_DIR/sync_pod.sh"

echo "=== LAUNCH blackout smoke $(date -u +%H:%M:%SZ) ==="
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" 'cd /workspace/Charybdis && sed -i "s/\r$//" scripts/pod/pod_blackout_smoke.sh && source .venv/bin/activate && nohup bash scripts/pod/pod_blackout_smoke.sh > /tmp/pod_blackout_stdout.log 2>&1 & echo blackout_pid=$!'
