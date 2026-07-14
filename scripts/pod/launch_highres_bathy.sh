#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

bash "$LOCAL_ROOT/scripts/pod/sync_pod.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
bash scripts/pod/pod_bootstrap_venv.sh
sed -i 's/\r$//' scripts/pod/pod_highres_bathy.sh
nohup bash scripts/pod/pod_highres_bathy.sh > /tmp/pod_highres_bathy_stdout.log 2>&1 &
echo highres_bathy_pid=$!
REMOTE
