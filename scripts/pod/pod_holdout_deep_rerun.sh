#!/usr/bin/env bash
# Re-run holdout deep release @ 256 after route fixes (pod only).
set -euo pipefail

REPO=/workspace/Charybdis
cd "$REPO"
LOG=/tmp/pod_holdout_deep_rerun.log
: >"$LOG"
ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export MPLBACKEND=Agg

WORKERS=31
STAMP="$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD 2>/dev/null || echo synced)"
OUT="artifacts/validation/${STAMP}/holdout_deep_rerun"
mkdir -p "$OUT"

log "=== holdout deep release 256 @ ${WORKERS} ==="
python scripts/hybrid_validate_deep_matrix.py \
  --tier release \
  --runs 256 \
  --workers "${WORKERS}" \
  --seeds validation/seeds_holdout_v1.txt \
  --allow-dirty \
  --output-dir "${OUT}/deep_release" 2>&1 | tee -a "$LOG"

python3 - <<'PY' | tee -a "$LOG"
import json, sys
from pathlib import Path

root = sorted(Path("artifacts/validation").glob("*/holdout_deep_rerun"), key=lambda p: p.stat().st_mtime)[-1]
summary = root / "deep_release" / "matrix_summary.json"
data = json.loads(summary.read_text())
print(f"holdout_deep pass={data['passed']}")
for name, sc in data["scenarios"].items():
    r = sc["results"]
    print(f"  {name}: {'PASS' if sc['assessment']['passed'] else 'FAIL'} cep95={r['cep95_m']:.3f} gps_jump={r['gps_reacquisition_jump_cep95_m']:.3f}")
if not data["passed"]:
    sys.exit(1)
print(f"HOLDOUT_DEEP_RERUN_COMPLETE {root}")
PY

log "HOLDOUT_DEEP_RERUN_DONE ${OUT}"
