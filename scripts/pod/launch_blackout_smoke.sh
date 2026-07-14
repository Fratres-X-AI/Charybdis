#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
bash "$LOCAL_ROOT/scripts/pod/sync_pod.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
source .venv/bin/activate
nohup bash scripts/pod/pod_blackout_smoke.sh > /tmp/pod_blackout_stdout.log 2>&1 &
echo blackout_pid=$!
REMOTE
