#!/usr/bin/env bash
# Install compatible PyTorch and verify a real CUDA op (not just is_available).
# H200 / H100 / A100 (Hopper/Ampere): CUDA 12.6 stable.
# Blackwell: CUDA 12.8+ nightly (or RunPod PyTorch 2.8 + cu128 template).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/pod/pod_env.sh
source "$SCRIPT_DIR/pod_env.sh"

echo "=== ENSURE POD CUDA pod=${POD_NAME} ==="

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis

# Prefer system python with torch; activate venv only if it already works.
if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate || true
fi
export PYTHONPATH=.

PY=python3
command -v python >/dev/null 2>&1 && PY=python

smoke() {
  "$PY" - <<'PY'
import sys
import torch
import torch.nn as nn

if not torch.cuda.is_available() or torch.cuda.device_count() < 1:
    print("SMOKE_FAIL no cuda")
    sys.exit(1)

for i in range(torch.cuda.device_count()):
    x = torch.randn(4, 8, 32, 32, device=f"cuda:{i}")
    m = nn.Conv2d(8, 16, 3, padding=1).to(f"cuda:{i}")
    y = m(x)
    torch.cuda.synchronize(i)
    print("SMOKE_OK", i, torch.cuda.get_device_name(i), "torch", torch.__version__, "out", tuple(y.shape))
PY
}

gpu_names="$(nvidia-smi -L 2>/dev/null || true)"
echo "$gpu_names"
ngpu=$(echo "$gpu_names" | grep -c 'GPU ' || true)
echo "GPU_COUNT=${ngpu}"

blackwell_gpu=0
if echo "$gpu_names" | grep -qi blackwell; then
  blackwell_gpu=1
fi

if smoke 2>/dev/null; then
  echo "CUDA already OK"
  exit 0
fi

echo "CUDA smoke failed — repairing PyTorch..."
pkill -f 'pip install' 2>/dev/null || true
sleep 2

if (( blackwell_gpu )); then
  echo "Blackwell detected — installing cu128 nightly torch"
  "$PY" -m pip install -q --force-reinstall torch --index-url https://download.pytorch.org/whl/nightly/cu128
else
  echo "Hopper/Ampere path — installing cu126 stable torch"
  "$PY" -m pip install -q --force-reinstall torch --index-url https://download.pytorch.org/whl/cu126
fi

if ! smoke; then
  echo "ERROR: CUDA smoke still failing after torch reinstall"
  nvidia-smi -L || true
  "$PY" -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())" || true
  exit 1
fi

echo "ENSURE_CUDA_OK"
REMOTE

echo "ENSURE_CUDA_DONE"
