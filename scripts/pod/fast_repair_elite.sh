#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
for f in scripts/pod/*.sh; do sed -i 's/\r$//' "$f"; chmod +x "$f"; done

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
python -m pip install -c requirements/ci.txt -e ".[dev]"
python -m pip install --force-reinstall --no-cache-dir numpy scipy
python -m pip install torch --index-url https://download.pytorch.org/whl/cu126

python - <<'PY'
import numpy, scipy, torch
print("OK numpy", numpy.__version__)
print("OK scipy", scipy.__version__)
print("OK torch", torch.__version__, "cuda", torch.cuda.is_available(), "count", torch.cuda.device_count())
PY

pkill -f pod_elite_phase34 || true
pkill -f hybrid_validate || true
pkill -f pod_quad_gpu || true
pkill -f pod_max_gpu_lane || true
pkill -f real_bathymetry_validate || true
sleep 2

: > /tmp/pod_elite_phase34_stdout.log
: > /tmp/pod_elite_phase34.log
nohup bash scripts/pod/pod_elite_phase34.sh > /tmp/pod_elite_phase34_stdout.log 2>&1 &
echo "elite_pid=$!"
sleep 8
echo "validate_workers=$(pgrep -c -f hybrid_validate 2>/dev/null || echo 0)"
echo "gpu_lanes=$(pgrep -c -f pod_max_gpu_lane 2>/dev/null || echo 0)"
pgrep -af 'pod_elite|hybrid_validate|pod_quad|pod_max_gpu' | head -15 || true
tail -6 /tmp/pod_elite_phase34.log 2>/dev/null || true
nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader 2>/dev/null || true
REMOTE

echo "FAST_REPAIR_DONE"
