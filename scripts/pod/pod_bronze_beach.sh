#!/usr/bin/env bash
# Beach close-out — max CPU: harbor+deep engineering in parallel (31+31 workers).
set -euo pipefail
REPO=/workspace/Charybdis
cd "$REPO"
LOG=/tmp/pod_bronze_beach.log
: >"$LOG"
ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export MPLBACKEND=Agg

STAMP=$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD 2>/dev/null || echo synced)
OUT="artifacts/validation/${STAMP}/beach_max"
mkdir -p "${OUT}"

log "=== patrol handoff regression (fast) ==="
python -m pytest tests/test_hybrid_patrol_handoffs.py -q 2>&1 | tee -a "$LOG"
log "PATROL_HANDOFF_OK"

log "=== MAX CPU: harbor+deep engineering 64 runs (31+31 workers) ==="
(
  python scripts/hybrid_validate_matrix.py \
    --tier engineering --runs 64 --workers 31 --allow-dirty \
    --output-dir "${OUT}/engineering" 2>&1 | tee "/tmp/pod_beach_harbor.log"
) &
pid_h=$!
(
  python scripts/hybrid_validate_deep_matrix.py \
    --tier engineering --runs 64 --workers 31 --allow-dirty \
    --output-dir "${OUT}/deep_engineering" 2>&1 | tee "/tmp/pod_beach_deep.log"
) &
pid_d=$!
wait "$pid_h" "$pid_d"

python - <<'PY' | tee -a "$LOG"
import json
import sys
from pathlib import Path

root = Path("artifacts/validation")
beach_dirs = sorted(root.glob("*/beach_max"), key=lambda p: p.stat().st_mtime)
if not beach_dirs:
    print("beach_max: no output dir")
    sys.exit(1)
out = beach_dirs[-1]
failed = []
for sub, label in (("engineering", "harbor"), ("deep_engineering", "deep")):
    summary = out / sub / "matrix_summary.json"
    if not summary.exists():
        failed.append(f"{label}: missing {summary}")
        continue
    data = json.loads(summary.read_text())
    if not data.get("passed"):
        failed.append(f"{label}: matrix_summary passed=false")
    else:
        print(f"{label}: PASS")
if failed:
    for item in failed:
        print(item)
    sys.exit(1)
PY
log "ENGINEERING_MATRIX_OK ${OUT}"

log "=== legacy stress 64 @ 31 workers ==="
python scripts/stress_run.py 64 2>&1 | tee "${OUT}/legacy_stress.log"
log "STRESS_OK"

log "BRONZE_BEACH_COMPLETE ${OUT}"
