#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
bash "$LOCAL_ROOT/scripts/pod/sync_pod.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
for s in pod_cpu_chain.sh pod_worst_sweep.sh; do sed -i "s/\r$//" "scripts/pod/$s"; done
source .venv/bin/activate
nohup bash scripts/pod/pod_cpu_chain.sh > /tmp/pod_cpu_chain_stdout.log 2>&1 &
echo chain_pid=$!
REMOTE
