#!/usr/bin/env bash
# Repair broken venv (numpy/scipy openblas) and relaunch elite pass.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

bash "$LOCAL_ROOT/scripts/pod/sync_pod.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
for f in scripts/pod/*.sh; do sed -i 's/\r$//' "$f"; chmod +x "$f"; done

echo "[repair] rebuilding venv"
pkill -f python || true
sleep 2
rm -rf .venv || true
find .venv -delete 2>/dev/null || true
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -q -U pip setuptools wheel
python -m pip install -q -c requirements/ci.txt -e ".[dev]"
python -m pip install -q torch --index-url https://download.pytorch.org/whl/cu126

python - <<'PY'
import numpy, scipy, torch
print("numpy", numpy.__version__)
print("scipy", scipy.__version__)
print("torch", torch.__version__, torch.cuda.is_available(), torch.cuda.device_count())
PY

pkill -f pod_elite_phase34 || true
pkill -f hybrid_validate || true
pkill -f pod_quad_gpu || true
pkill -f pod_max_gpu_lane || true
sleep 2

nohup bash scripts/pod/pod_elite_phase34.sh > /tmp/pod_elite_phase34_stdout.log 2>&1 &
echo "elite_pid=$!"
sleep 5
echo "validate_workers=$(pgrep -c -f hybrid_validate 2>/dev/null || echo 0)"
pgrep -af 'pod_elite|hybrid_validate|pod_quad|pod_max_gpu' | head -12 || true
tail -8 /tmp/pod_elite_phase34_stdout.log 2>/dev/null || true
nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader 2>/dev/null || true
REMOTE

echo "REPAIR_RELAUNCH_DONE"
