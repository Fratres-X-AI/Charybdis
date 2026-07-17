#!/usr/bin/env bash
# Sync + bootstrap + launch GPU-only SO(2) matcher training on the active pod.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=scripts/pod/pod_env.sh
source "$SCRIPT_DIR/pod_env.sh"

echo "=== GPU TRAIN LAUNCH pod=${POD_NAME} ==="
bash "$LOCAL_ROOT/scripts/pod/sync_pod.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
for f in scripts/pod/*.sh; do
  sed -i 's/\r$//' "$f"
  chmod +x "$f"
done

if [[ ! -d .venv ]]; then
  bash scripts/pod/pod_bootstrap_venv.sh
fi
source .venv/bin/activate
python -m pip install -q -c requirements/ci.txt -e ".[dev]"

if ! python - <<'PY'
import sys
try:
    import torch
except Exception:
    sys.exit(1)
sys.exit(0 if torch.cuda.is_available() and torch.cuda.device_count() > 0 else 1)
PY
then
  echo "[bootstrap] installing CUDA torch"
  python -m pip install -q --force-reinstall torch --index-url https://download.pytorch.org/whl/cu126
fi

python - <<'PY'
import torch
print("torch", torch.__version__, "cuda", torch.cuda.is_available(), "gpus", torch.cuda.device_count(), flush=True)
if not torch.cuda.is_available() or torch.cuda.device_count() < 1:
    raise SystemExit("ERROR no CUDA GPUs visible")
for i in range(torch.cuda.device_count()):
    print(f"gpu{i} {torch.cuda.get_device_name(i)}", flush=True)
PY

mkdir -p models charybdis/models
if [[ ! -f models/tcm_so2.pt ]]; then
  if [[ -f charybdis/models/tcm_so2.pt ]]; then
    cp -f charybdis/models/tcm_so2.pt models/tcm_so2.pt
  else
    echo "ERROR missing models/tcm_so2.pt after sync"
    exit 1
  fi
fi

echo "[cleanup] stopping old GPU lanes"
pkill -f pod_quad_gpu_max || true
pkill -f pod_dual_gpu_max || true
pkill -f pod_max_gpu_lane || true
sleep 2
rm -f /tmp/pod_quad_gpu.log /tmp/pod_dual_gpu.log /tmp/pod_gpu_lane*.log

echo "[launch] GPU-only SO2 lanes"
nohup bash scripts/pod/pod_quad_gpu_max.sh > /tmp/pod_quad_gpu.out 2>&1 &
sleep 5

echo "=== GPU TRAIN STATUS ==="
echo "launcher_pid=$(pgrep -f 'pod_quad_gpu_max.sh' | tr '\n' ' ' || true)"
echo "lane_count=$(pgrep -c -f 'pod_max_gpu_lane.sh' 2>/dev/null || echo 0)"
pgrep -af 'pod_quad_gpu_max|pod_max_gpu_lane' || true
nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,power.draw --format=csv,noheader 2>/dev/null || true
REMOTE

echo "GPU_TRAIN_LAUNCHED - babysit with: bash scripts/pod/go_babysit_gpu.sh"
