#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
bash "$LOCAL_ROOT/scripts/pod/sync_pod.sh"
scp -P "$POD_PORT" -i "$POD_KEY" "$SCRIPT_DIR/pod_gebco_job.sh" "$POD_HOST:/workspace/Charybdis/scripts/pod/"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
sed -i 's/\r$//' scripts/pod/pod_gebco_job.sh
source .venv/bin/activate
nohup bash scripts/pod/pod_gebco_job.sh > /tmp/pod_gebco_stdout.log 2>&1 &
echo gebco_pid=$!
REMOTE
