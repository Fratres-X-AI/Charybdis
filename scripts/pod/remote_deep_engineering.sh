#!/usr/bin/env bash
set -euo pipefail
cd /workspace/Charybdis
source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
STAMP=$(date -u +"%Y%m%dT%H%M%SZ")
SHA=$(git rev-parse --short HEAD 2>/dev/null || echo synced)
OUT="artifacts/validation/${STAMP}-${SHA}/deep_engineering"
echo "[$(date -u +%H:%M:%S)] deep engineering start out=${OUT}"
python scripts/hybrid_validate_deep_matrix.py \
  --tier engineering \
  --runs 64 \
  --workers 31 \
  --allow-dirty \
  --output-dir "$OUT" \
  2>&1 | tee /tmp/pod_deep_matrix.log
echo "DEEP_ENGINEERING_DONE" >>/tmp/pod_deep_matrix.log
