#!/usr/bin/env bash
# Re-sync and relaunch deep engineering only (harbor may still be running).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOST=root@195.26.233.70
PORT=55580
KEY="${HOME}/.ssh/id_ed25519"

bash "$SCRIPT_DIR/sync_pod_a100.sh"

ssh -p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no "$HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
pkill -f hybrid_validate_deep_matrix || true
sleep 2
source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
SHA=$(git rev-parse --short HEAD 2>/dev/null || echo synced)
OUT="artifacts/validation/${STAMP}-${SHA}/deep_engineering"
nohup python scripts/hybrid_validate_deep_matrix.py \
  --tier engineering \
  --runs 64 \
  --workers 31 \
  --allow-dirty \
  --output-dir "$OUT" \
  > /tmp/pod_deep_matrix.log 2>&1 &
echo "deep_relaunch pid=$! out=$OUT head=$SHA"
REMOTE
