#!/usr/bin/env bash
# Launch deep-ocean release matrix (256 runs) on A100 while GPU trains.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOST=root@195.26.233.70
PORT=55580
KEY="${HOME}/.ssh/id_ed25519"

bash "$SCRIPT_DIR/sync_pod_a100.sh"

ssh -p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no "$HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
SHA=$(git rev-parse --short HEAD 2>/dev/null || echo synced)
OUT="artifacts/validation/${STAMP}-${SHA}/deep_release"
nohup python scripts/hybrid_validate_deep_matrix.py \
  --tier release \
  --runs 256 \
  --workers 31 \
  --allow-dirty \
  --output-dir "$OUT" \
  > /tmp/pod_deep_release.log 2>&1 &
echo "deep_release pid=$! out=$OUT head=$SHA"
REMOTE
