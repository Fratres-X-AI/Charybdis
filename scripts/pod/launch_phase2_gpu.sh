#!/usr/bin/env bash
# Resume Phase 2 + dual GPU (skip Phase 1 — already passed).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOST=root@157.157.221.29
PORT=30511
KEY="${HOME}/.ssh/id_ed25519"

bash "$SCRIPT_DIR/sync_pod_dual.sh"

ssh -p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no "$HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
pkill -f hybrid_validate || true
pkill -f pod_dual || true
pkill -f pod_max_gpu || true
sleep 2
source .venv/bin/activate
nohup bash -c '
  source .venv/bin/activate
  cd /workspace/Charybdis
  bash scripts/pod/pod_dual_matrix.sh engineering 64
  bash scripts/pod/pod_dual_matrix.sh release 256
  bash scripts/pod/pod_dual_gpu_max.sh
' > /tmp/pod_phase2_gpu.out 2>&1 &
echo "resumed phase2+gpu on $(nproc) cpus"
REMOTE
