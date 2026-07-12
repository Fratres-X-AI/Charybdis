#!/usr/bin/env bash
set -euo pipefail
cd /workspace/Charybdis
pkill -f pod_max_gpu_lane 2>/dev/null || true
pkill -f pod_dual_gpu_max 2>/dev/null || true
sleep 2
if [[ -d .venv ]]; then
  mv .venv ".venv.bak.$(date +%s)" || true
fi
python3 -m venv .venv
source .venv/bin/activate
pip install -q -U pip
pip install -q -c requirements/ci.txt -e ".[dev]"
pip install -q torch --index-url https://download.pytorch.org/whl/cu126
nohup bash scripts/pod/pod_dual_gpu_max.sh > /tmp/pod_dual_gpu_retry.out 2>&1 &
echo "gpu_restarted gpus=$(nvidia-smi -L | wc -l)"
