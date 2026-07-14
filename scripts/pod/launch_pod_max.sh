#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
bash "$LOCAL_ROOT/scripts/pod/sync_pod.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
for s in pod_max_out.sh pod_highres_bathy.sh; do sed -i "s/\r$//" "scripts/pod/$s"; done
bash scripts/pod/pod_bootstrap_venv.sh
pkill -f pod_live_updates || true
pkill -f live_updates_30m || true
nohup bash scripts/pod/pod_max_out.sh > /tmp/pod_max_out_stdout.log 2>&1 &
echo max_out_pid=$!
echo cpus=$(nproc) gpus=$(nvidia-smi -L 2>/dev/null | wc -l)
REMOTE
