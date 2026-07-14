#!/usr/bin/env bash
# Integration-grade validation — pod only (31 workers max).
set -euo pipefail
REPO=/workspace/Charybdis
cd "$REPO"
LOG=/tmp/pod_integration_grade.log
: >"$LOG"
ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export MPLBACKEND=Agg

log "=== Phase 1: fast pytest (replay + patrol + contracts) ==="
python -m pytest --timeout=120 --timeout-method=thread \
  tests/test_hybrid_replay.py \
  tests/test_hybrid_patrol_handoffs.py \
  tests/test_hybrid_deep_validation.py -m "not slow" -q 2>&1 | tee -a "$LOG"
log "PHASE1_OK"

log "=== Phase 2: MAX CPU harbor+deep engineering 64x7 @ 31+31 workers ==="
STAMP=$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD 2>/dev/null || echo synced)
OUT="artifacts/validation/${STAMP}/integration_grade"
mkdir -p "${OUT}"
(
  python scripts/hybrid_validate_matrix.py \
    --tier engineering --runs 64 --workers 31 --allow-dirty \
    --output-dir "${OUT}/engineering" 2>&1 | tee "/tmp/pod_int_harbor.log"
) &
pid_h=$!
(
  python scripts/hybrid_validate_deep_matrix.py \
    --tier engineering --runs 64 --workers 31 --allow-dirty \
    --output-dir "${OUT}/deep_engineering" 2>&1 | tee "/tmp/pod_int_deep.log"
) &
pid_d=$!
wait "$pid_h" "$pid_d"
python - <<'PY' | tee -a "$LOG"
import json, sys
from pathlib import Path
root = sorted(Path("artifacts/validation").glob("*/integration_grade"), key=lambda p: p.stat().st_mtime)[-1]
for sub, label in (("engineering", "harbor"), ("deep_engineering", "deep")):
    s = root / sub / "matrix_summary.json"
    d = json.loads(s.read_text())
    if not d.get("passed"):
        print(f"FAIL {label}")
        sys.exit(1)
    print(f"PASS {label} ({len(d.get('scenarios', d))} scenarios)")
PY
log "PHASE2_OK ${OUT}"

log "INTEGRATION_GRADE_COMPLETE"
