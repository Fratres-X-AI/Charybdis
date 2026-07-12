#!/usr/bin/env bash
set -euo pipefail
HOST=root@157.157.221.29
PORT=30511
KEY="${HOME}/.ssh/id_ed25519"

ssh -p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no "$HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
pkill -f hybrid_validate_deep_matrix || true
sleep 1
source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT="artifacts/validation/${STAMP}-synced/deep_engineering"
nohup python scripts/hybrid_validate_deep_matrix.py \
  --tier engineering \
  --runs 64 \
  --workers 31 \
  --allow-dirty \
  --output-dir "$OUT" \
  > /tmp/pod_deep_matrix.log 2>&1 &
echo "launched deep engineering pid=$! out=$OUT cpus=$(nproc)"
REMOTE
