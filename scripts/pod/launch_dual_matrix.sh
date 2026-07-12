#!/usr/bin/env bash
# Sync, ensure venv, launch dual 31+31 worker matrices immediately.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOST=root@157.157.221.29
PORT=30511
KEY="${HOME}/.ssh/id_ed25519"

bash "$SCRIPT_DIR/sync_pod_dual.sh"

ssh -p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no "$HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
pkill -f pod_dual_sprint || true
pkill -f hybrid_validate || true
pkill -f pod_dual_matrix || true
sleep 2

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install -q -U pip
python -m pip install -q -c requirements/ci.txt -e ".[dev]"

nohup bash scripts/pod/pod_dual_matrix.sh engineering 64 > /tmp/pod_dual_matrix.out 2>&1 &
echo "launched dual matrix engineering 31+31 on $(nproc) cpus"
REMOTE
