#!/usr/bin/env bash
# Max out H200 pod: push elite scripts, CPU validation parallel, H200 round-2 watcher.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=scripts/pod/pod_env.sh
source "$SCRIPT_DIR/pod_env.sh"

echo "=== SATURATE H200 pod=${POD_NAME} ==="

tar -C "$LOCAL_ROOT/scripts/pod" --no-same-owner --no-same-permissions -cf - \
  pod_cpu_elite_parallel.sh \
  pod_h200_max_gpu_lane.sh \
  pod_h200_followon.sh \
  pod_full_pass.sh \
  pod_hotzone_bathy.sh \
  pod_heal_h200.sh \
  gpu_progress.sh \
  kick_gpu_now.sh \
  kick_saturate_h200.sh \
  babysit_gpu.sh \
  gpu_status.sh \
  pod_quad_gpu_max.sh \
  2>/dev/null | ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
  "mkdir -p /workspace/Charybdis/scripts/pod && tar --no-same-owner -xf - -C /workspace/Charybdis/scripts/pod && chmod +x /workspace/Charybdis/scripts/pod/*.sh"

tar -C "$LOCAL_ROOT" --no-same-owner --no-same-permissions -cf - \
  validation/hotzone_gebco_regions.json \
  scripts/prepare_gebco_tile.py \
  2>/dev/null | ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
  "tar --no-same-owner -xf - -C /workspace/Charybdis"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
for f in scripts/pod/*.sh; do sed -i 's/\r$//' "$f"; chmod +x "$f"; done

if pgrep -f pod_cpu_elite_parallel >/dev/null 2>&1; then
  echo "cpu_elite already running"
else
  echo "[launch] CPU elite parallel (6 jobs @ 16 workers)"
  nohup bash scripts/pod/pod_cpu_elite_parallel.sh > /tmp/pod_cpu_elite_stdout.log 2>&1 &
fi

if pgrep -f pod_h200_followon >/dev/null 2>&1; then
  echo "h200_followon already running"
else
  echo "[launch] H200 round-2 watcher (auto after round-1)"
  nohup bash scripts/pod/pod_h200_followon.sh > /tmp/pod_h200_followon_stdout.log 2>&1 &
fi

if pgrep -f pod_hotzone_bathy >/dev/null 2>&1; then
  echo "hotzone already running"
else
  echo "[launch] hotzone GEBCO (8 regions)"
  nohup bash scripts/pod/pod_hotzone_bathy.sh > /tmp/pod_hotzone_bathy_stdout.log 2>&1 &
fi

sleep 3
echo "=== SATURATE STATUS ==="
echo "gpu_lanes=$(pgrep -c -f 'pod_max_gpu_lane.sh' 2>/dev/null || echo 0)"
echo "cpu_elite=$(pgrep -c -f 'hybrid_validate' 2>/dev/null || echo 0)"
echo "followon=$(pgrep -c -f 'pod_h200_followon' 2>/dev/null || echo 0)"
pgrep -af 'pod_max_gpu_lane|pod_h200_followon|hybrid_validate|pod_highres' | head -20 || true
uptime
nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader
REMOTE

echo "SATURATE_H200_DONE"
