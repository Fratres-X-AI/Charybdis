#!/usr/bin/env bash
# Kill duplicate chaos, launch 4 pinned CPU clusters + 4 GPU lanes. Git Bash only.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

echo "=== QUAD CLUSTER LAUNCH: ${POD_NAME} ==="
bash "$LOCAL_ROOT/scripts/pod/sync_pod.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
for f in scripts/pod/*.sh; do sed -i 's/\r$//' "$f"; chmod +x "$f"; done

echo "[cleanup] stopping duplicate validation + old orchestrators"
pkill -f pod_elite_phase34 || true
pkill -f pod_elite_parallel || true
pkill -f pod_quad_cluster || true
pkill -f pod_hybrid_phase2 || true
pkill -f pod_max_out || true
pkill -f pod_worst_sweep || true
pkill -f pod_integration_grade || true
pkill -f pod_release_grade || true
pkill -f hybrid_validate || true
pkill -f real_bathymetry_validate || true
pkill -f pod_max_gpu_lane || true
sleep 3
echo "remaining_validate=$(pgrep -c -f hybrid_validate 2>/dev/null || echo 0)"

source .venv/bin/activate
# Blackwell GPU torch
python -m pip install -q torch --index-url https://download.pytorch.org/whl/cu130 2>/dev/null || true

echo "[launch] 4 CPU clusters @ 28 workers (taskset 0-27/28-55/56-83/84-111)"
nohup bash scripts/pod/pod_quad_cluster.sh > /tmp/pod_quad_cluster_stdout.log 2>&1 &
qpid=$!

echo "[launch] 4 GPU lanes in parallel"
for gpu in 0 1 2 3; do
  case "$gpu" in 0) lane=a ;; 1) lane=b ;; 2) lane=c ;; 3) lane=d ;; esac
  nohup bash scripts/pod/pod_max_gpu_lane.sh "$gpu" "$lane" > "/tmp/pod_gpu_lane${gpu}.log" 2>&1 &
done

sleep 6
echo "=== QUAD STATUS ==="
echo "quad_pid=$qpid"
echo "validate_procs=$(pgrep -c -f hybrid_validate 2>/dev/null || echo 0)"
echo "gpu_lanes=$(pgrep -c -f 'pod_max_gpu_lane.sh' 2>/dev/null || echo 0)"
echo "load=$(cat /proc/loadavg)"
pgrep -af 'pod_quad_cluster|hybrid_validate|pod_max_gpu_lane' | head -16 || true
tail -8 /tmp/pod_quad_cluster.log 2>/dev/null || tail -8 /tmp/pod_quad_cluster_stdout.log 2>/dev/null || true
nvidia-smi --query-gpu=index,utilization.gpu,memory.used,power.draw --format=csv,noheader 2>/dev/null || true
REMOTE

echo "QUAD_CLUSTER_LAUNCHED — poll: bash scripts/pod/poll_quad_cluster.sh"
