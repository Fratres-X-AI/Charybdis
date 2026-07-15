#!/usr/bin/env bash
# Sync + detach full Jul-15 recovery pipeline on active pod (Git Bash only).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

echo "=== RECOVER DAY: ${POD_NAME} (${POD_HOST}:${POD_PORT}) ==="
bash "$LOCAL_ROOT/scripts/pod/sync_pod.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
for f in scripts/pod/*.sh; do sed -i 's/\r$//' "$f"; chmod +x "$f"; done

pkill -f pod_recover_day || true
pkill -f pod_metric_sprint || true
pkill -f pod_max_out || true
pkill -f hybrid_validate || true
pkill -f real_bathymetry_validate || true
sleep 2

nohup bash scripts/pod/pod_recover_day.sh > /tmp/pod_recover_day_stdout.log 2>&1 &
echo "recover_pid=$!"
sleep 2
echo "cpus=$(nproc) gpus=$(nvidia-smi -L 2>/dev/null | wc -l)"
pgrep -af 'pod_recover_day|pod_metric|pod_max|hybrid_validate|real_bathymetry' | head -12 || echo idle
tail -6 /tmp/pod_recover_day_stdout.log 2>/dev/null || true
REMOTE

echo "=== LAUNCHED — poll: bash scripts/pod/poll_recover_day.sh ==="
