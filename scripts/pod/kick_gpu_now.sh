#!/usr/bin/env bash
# Launch GPU training on active pod WITHOUT re-syncing. Git Bash only.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/pod/pod_env.sh
source "$SCRIPT_DIR/pod_env.sh"

echo "=== KICK GPU NOW pod=${POD_NAME} ==="

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
for f in scripts/pod/*.sh; do sed -i 's/\r$//' "$f"; chmod +x "$f"; done

if [[ ! -d .venv ]]; then
  echo "[bootstrap] creating venv"
  bash scripts/pod/pod_bootstrap_venv.sh
fi
source .venv/bin/activate
export PYTHONPATH=.
python -m pip install -q -c requirements/ci.txt -e ".[dev]" 2>/dev/null || true

if ! python -c "import torch; assert torch.cuda.is_available() and torch.cuda.device_count()>=1" 2>/dev/null; then
  echo "[bootstrap] installing CUDA torch"
  python -m pip install -q --force-reinstall torch --index-url https://download.pytorch.org/whl/cu126
fi

python - <<'PY'
import torch
print("torch", torch.__version__, "gpus", torch.cuda.device_count(), flush=True)
for i in range(torch.cuda.device_count()):
    print(f"gpu{i} {torch.cuda.get_device_name(i)}", flush=True)
if not torch.cuda.is_available() or torch.cuda.device_count() < 1:
    raise SystemExit("ERROR no CUDA GPUs")
PY

mkdir -p models
test -f models/tcm_so2.pt || { echo "ERROR missing models/tcm_so2.pt"; exit 1; }

pkill -f pod_quad_gpu_max || true
pkill -f pod_max_gpu_lane || true
sleep 2
rm -f /tmp/pod_gpu_lane*.log /tmp/pod_quad_gpu.log /tmp/pod_quad_gpu.out

echo "[launch] pod_quad_gpu_max.sh"
nohup bash scripts/pod/pod_quad_gpu_max.sh > /tmp/pod_quad_gpu.out 2>&1 &
sleep 10

echo "=== STATUS ==="
echo "lanes=$(pgrep -c -f 'pod_max_gpu_lane.sh' 2>/dev/null || echo 0)"
pgrep -af 'pod_quad_gpu_max|pod_max_gpu_lane' || true
nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used --format=csv,noheader
for g in 0 1; do
  echo "--- lane${g} tail ---"
  tail -5 "/tmp/pod_gpu_lane${g}.log" 2>/dev/null || echo "(no log yet)"
done
tail -10 /tmp/pod_quad_gpu.out 2>/dev/null || true
REMOTE

echo "KICK_GPU_NOW_DONE"
