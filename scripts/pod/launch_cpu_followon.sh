#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
bash "$LOCAL_ROOT/scripts/pod/sync_pod.sh"
scp -P "$POD_PORT" -i "$POD_KEY" "$SCRIPT_DIR/pod_cpu_followon.sh" "$SCRIPT_DIR/pod_cpu_chain.sh" "$POD_HOST:/workspace/Charybdis/scripts/pod/"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
sed -i 's/\r$//' scripts/pod/pod_cpu_followon.sh scripts/pod/pod_cpu_chain.sh
source .venv/bin/activate
nohup bash scripts/pod/pod_cpu_followon.sh > /tmp/pod_cpu_followon_stdout.log 2>&1 &
echo followon_pid=$!
REMOTE
