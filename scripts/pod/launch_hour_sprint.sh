#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
bash "$LOCAL_ROOT/scripts/pod/sync_pod.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
for s in pod_hour_sprint.sh pod_highres_bathy.sh; do sed -i "s/\r$//" "scripts/pod/$s"; done
bash scripts/pod/pod_bootstrap_venv.sh
nohup bash scripts/pod/pod_hour_sprint.sh > /tmp/pod_hour_sprint_stdout.log 2>&1 &
echo hour_sprint_pid=$!
REMOTE
