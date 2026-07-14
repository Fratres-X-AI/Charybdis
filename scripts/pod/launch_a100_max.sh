#!/usr/bin/env bash
# Sync + bootstrap + max CPU validation + A100 GPU training (Git Bash / Linux SSH only).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOST=root@195.26.233.70
PORT=55580
KEY="${HOME}/.ssh/id_ed25519"

bash "$SCRIPT_DIR/sync_pod_a100.sh"

ssh -p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no "$HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
pkill -f hybrid_validate || true
pkill -f pod_dual_matrix || true
pkill -f pod_max_gpu_lane || true
pkill -f pod_dual_gpu_max || true
sleep 2

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m ensurepip --upgrade 2>/dev/null || true
python -m pip install -q -U pip setuptools wheel
python -m pip install -q -c requirements/ci.txt -e ".[dev]"
python -m pip install -q torch --index-url https://download.pytorch.org/whl/cu126
python -c "import torch; print('torch_ok', torch.cuda.device_count(), torch.cuda.get_device_name(0))"

mkdir -p models
test -f models/tcm_so2.pt || { echo "ERROR missing models/tcm_so2.pt after sync"; exit 1; }

nohup bash scripts/pod/pod_dual_matrix.sh engineering 64 > /tmp/pod_dual_matrix.out 2>&1 &
nohup bash scripts/pod/pod_max_gpu_lane.sh 0 a > /tmp/pod_gpu_lane0.log 2>&1 &
sleep 4
echo "=== launched ==="
pgrep -af "hybrid_validate|pod_max_gpu_lane" || true
nvidia-smi --query-gpu=index,utilization.gpu,memory.used,power.draw --format=csv,noheader
uptime
REMOTE
