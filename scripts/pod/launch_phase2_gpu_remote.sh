#!/usr/bin/env bash
set -euo pipefail
cd /workspace/Charybdis
pkill -f pod_max_gpu_lane 2>/dev/null || true
pkill -f pod_dual_gpu_max 2>/dev/null || true
pkill -f hybrid_validate 2>/dev/null || true
sleep 2
source .venv/bin/activate 2>/dev/null || true
nohup bash -c '
  source .venv/bin/activate
  cd /workspace/Charybdis
  bash scripts/pod/pod_dual_matrix.sh engineering 64
  bash scripts/pod/pod_dual_matrix.sh release 256
  bash scripts/pod/pod_dual_gpu_max.sh
' > /tmp/pod_phase2_gpu.out 2>&1 &
echo phase2_gpu_resumed
