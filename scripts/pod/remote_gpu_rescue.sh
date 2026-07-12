#!/usr/bin/env bash
set -euo pipefail

cd /workspace/Charybdis

ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*"; }

log "rescue start"
log "processes"
pgrep -af "go_gpu_now|pip install torch|pod_max_gpu_lane|pod_dual_gpu_max|hybrid_validate|pod_dual_full" || true

log "kill non-gpu/full jobs"
pkill -f "pod_dual_full.sh" || true
pkill -f "hybrid_validate" || true
pkill -f "phase1_pod" || true
sleep 2

if pgrep -f "python -m pip install torch" >/dev/null; then
  log "kill hung torch install"
  pkill -f "python -m pip install torch" || true
  sleep 2
fi
if pgrep -f "go_gpu_now.sh" >/dev/null; then
  log "kill hung go_gpu_now"
  pkill -f "go_gpu_now.sh" || true
  sleep 2
fi

source .venv/bin/activate

log "repair pip"
python -m ensurepip --upgrade
python -m pip install -U pip setuptools wheel

log "install torch if needed"
python - <<'PY' || python -m pip install torch --index-url https://download.pytorch.org/whl/cu126
import torch
print("torch_present", torch.__version__, torch.cuda.is_available(), torch.cuda.device_count())
PY

log "verify cuda"
python - <<'PY'
import torch
print("torch_ok", torch.__version__, torch.cuda.is_available(), torch.cuda.device_count())
for idx in range(torch.cuda.device_count()):
    print("gpu", idx, torch.cuda.get_device_name(idx))
PY

log "launch dual gpu"
pkill -f "pod_max_gpu_lane.sh" || true
pkill -f "pod_dual_gpu_max.sh" || true
rm -f /tmp/pod_gpu_lane0.log /tmp/pod_gpu_lane1.log /tmp/pod_dual_gpu.log /tmp/gpu_go.out
nohup bash scripts/pod/pod_dual_gpu_max.sh > /tmp/gpu_go.out 2>&1 &
sleep 5

log "post-launch processes"
pgrep -af "pod_max_gpu_lane|pod_dual_gpu_max" || true
nvidia-smi --query-gpu=index,utilization.gpu,memory.used,power.draw --format=csv,noheader
