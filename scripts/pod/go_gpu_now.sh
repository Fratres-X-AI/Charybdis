#!/usr/bin/env bash
set -euo pipefail
cd /workspace/Charybdis
pkill -f pod_max_gpu_lane 2>/dev/null || true
pkill -f pod_dual_gpu_max 2>/dev/null || true
for d in .venv .venv.broken.*; do
  [[ -e "$d" ]] || continue
  chmod -R u+w "$d" 2>/dev/null || true
  rm -rf "$d" || mv "$d" "/tmp/$(basename "$d").$(date +%s)" || true
done
python3 -m venv .venv
source .venv/bin/activate
python -m ensurepip --upgrade
python -m pip install -U pip setuptools wheel
python -m pip install -c requirements/ci.txt -e ".[dev]"
python -m pip install torch --index-url https://download.pytorch.org/whl/cu126
python -c "import torch; print('torch_ok', torch.cuda.device_count(), torch.cuda.get_device_name(0))"
nohup bash scripts/pod/pod_dual_gpu_max.sh > /tmp/gpu_go.out 2>&1 &
sleep 3
pgrep -af pod_max_gpu || true
nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader
