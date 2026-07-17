#!/usr/bin/env bash
# Push hotzone/green fixes and relaunch hotzone ONLY — do not touch GPU R2.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=scripts/pod/pod_env.sh
source "$SCRIPT_DIR/pod_env.sh"

echo "=== PUSH HOTZONE FIX (GPUs untouched) pod=${POD_NAME} ==="

tar -C "$LOCAL_ROOT" --no-same-owner --no-same-permissions -cf - \
  validation/hotzone_gebco_regions.json \
  scripts/pod/pod_hotzone_bathy.sh \
  scripts/pod/pod_pipeline_green.sh \
  | ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
    "tar --no-same-owner -xf - -C /workspace/Charybdis && chmod +x /workspace/Charybdis/scripts/pod/*.sh && sed -i 's/\r$//' /workspace/Charybdis/scripts/pod/pod_hotzone_bathy.sh /workspace/Charybdis/scripts/pod/pod_pipeline_green.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
# Kill only hotzone / prepare — never GPU lanes
pkill -f 'pod_hotzone_bathy|prepare_gebco_tile|real_bathymetry.*hotzone' 2>/dev/null || true
sleep 2
if [[ -f .venv/bin/activate ]]; then source .venv/bin/activate; fi
export PYTHONPATH=.
nohup bash scripts/pod/pod_hotzone_bathy.sh > /tmp/pod_hotzone_bathy_stdout.log 2>&1 &
echo "hotzone_pid=$!"
sleep 3
pgrep -af pod_hotzone_bathy | head -3 || true
# Confirm R2 still alive
echo "r2=$(pgrep -c -f pod_h200_max_gpu_lane || echo 0)"
nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader
REMOTE

echo "HOTZONE_FIX_PUSHED"
