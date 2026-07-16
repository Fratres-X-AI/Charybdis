#!/usr/bin/env bash
# Sync + detach Phase 3+4 elite pass (Git Bash only).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

echo "=== ELITE PHASE 3+4: ${POD_NAME} (${POD_HOST}:${POD_PORT}) ==="
bash "$LOCAL_ROOT/scripts/pod/sync_pod.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
for f in scripts/pod/*.sh; do sed -i 's/\r$//' "$f"; chmod +x "$f"; done

pkill -f pod_elite_phase34 || true
pkill -f pod_hybrid_phase2 || true
pkill -f pod_quad_gpu_max || true
pkill -f pod_max_gpu_lane || true
pkill -f pod_max_out || true
pkill -f hybrid_validate || true
pkill -f real_bathymetry_validate || true
sleep 2

nohup bash scripts/pod/pod_elite_phase34.sh > /tmp/pod_elite_phase34_stdout.log 2>&1 &
echo "elite_pid=$!"
sleep 3
echo "cpus=$(nproc) load=$(cat /proc/loadavg)"
echo "validate_workers=$(pgrep -c -f hybrid_validate 2>/dev/null || echo 0)"
pgrep -af 'pod_elite_phase34|pod_hybrid_phase2|pod_10pass|hybrid_validate|real_bathymetry' 2>/dev/null | head -20 || echo idle
tail -10 /tmp/pod_elite_phase34_stdout.log 2>/dev/null || true
REMOTE

echo "=== LAUNCHED — babysit: bash scripts/pod/babysit_elite_phase34.sh ==="
