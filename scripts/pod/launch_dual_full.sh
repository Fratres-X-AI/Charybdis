#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOST=root@157.157.221.29
PORT=30511
KEY="${HOME}/.ssh/id_ed25519"

bash "$SCRIPT_DIR/sync_pod_dual.sh"

ssh -p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no "$HOST" "mkdir -p /workspace/Charybdis/models"

scp -P "$PORT" -i "$KEY" -o StrictHostKeyChecking=no \
  "${LOCAL_ROOT}/models/tcm_so2.pt" \
  "${HOST}:/workspace/Charybdis/models/tcm_so2.pt"

ssh -p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no "$HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
mkdir -p models
pkill -f pod_dual || true
pkill -f hybrid_validate || true
pkill -f pod_max_gpu || true
pkill -f phase1_pod || true
sleep 2
nohup bash scripts/pod/pod_dual_full.sh > /tmp/pod_dual_full.out 2>&1 &
echo "launched pod_dual_full: phase1 -> dual CPU 31+31 -> dual GPU max"
echo "cpus=$(nproc) gpus=$(nvidia-smi -L 2>/dev/null | wc -l)"
REMOTE
