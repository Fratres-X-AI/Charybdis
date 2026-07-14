#!/usr/bin/env bash
# Quick validation: deep_long_blackout only @ 31 workers.
set -euo pipefail
REPO=/workspace/Charybdis
cd "$REPO"
source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
STAMP=$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD 2>/dev/null || echo synced)-$$
OUT="artifacts/validation/${STAMP}/blackout_smoke"
python scripts/hybrid_validate_deep_matrix.py \
  --tier engineering --runs 64 --workers 31 --allow-dirty \
  --scenarios deep_long_blackout \
  --output-dir "$OUT" 2>&1 | tee /tmp/pod_blackout_smoke.log
python3 -c "import json; d=json.load(open('$OUT/matrix_summary.json')); assert d['passed'], d; print('BLACKOUT_SMOKE_PASS')"
