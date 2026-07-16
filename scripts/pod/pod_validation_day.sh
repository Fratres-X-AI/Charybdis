#!/usr/bin/env bash
# Jul 16 validation burst: mission 256 -> highres eng+release -> holdout release harbor+deep.
set -euo pipefail

REPO=/workspace/Charybdis
cd "$REPO"
LOG=/tmp/pod_validation_day.log
: >"$LOG"
ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 MKL_NUM_THREADS=1
export MPLBACKEND=Agg

WORKERS=31
STAMP="$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD 2>/dev/null || echo synced)"
OUT="artifacts/validation/${STAMP}/validation_day"
mkdir -p "$OUT"

log "=== 1/3 mission engineering matrix 256 @ ${WORKERS} ==="
python scripts/hybrid_validate_mission_matrix.py \
  --tier engineering \
  --runs 256 \
  --workers "${WORKERS}" \
  --allow-dirty \
  --output-dir "${OUT}/mission_engineering" 2>&1 | tee -a "$LOG"

log "=== 2/3 highres NOAA eng+release @ ${WORKERS} ==="
bash scripts/pod/pod_highres_bathy.sh 2>&1 | tee -a "$LOG"

log "=== 3/3 holdout release 256 harbor then deep @ ${WORKERS} ==="
python scripts/hybrid_validate_matrix.py \
  --tier release \
  --runs 256 \
  --workers "${WORKERS}" \
  --seeds validation/seeds_holdout_v1.txt \
  --allow-dirty \
  --output-dir "${OUT}/holdout_release/harbor_release" 2>&1 | tee "${OUT}/holdout_harbor.log"

python scripts/hybrid_validate_deep_matrix.py \
  --tier release \
  --runs 256 \
  --workers "${WORKERS}" \
  --seeds validation/seeds_holdout_v1.txt \
  --allow-dirty \
  --output-dir "${OUT}/holdout_release/deep_release" 2>&1 | tee "${OUT}/holdout_deep.log"

python3 - <<'PY' | tee -a "$LOG"
import json, sys
from pathlib import Path

root = sorted(Path("artifacts/validation").glob("*/validation_day"), key=lambda p: p.stat().st_mtime)[-1]
mission = root / "mission_engineering" / "matrix_summary.json"
if mission.exists():
    m = json.loads(mission.read_text())
    print(f"mission pass={m['passed']} scenarios={len(m['scenarios'])}")
    if not m["passed"]:
        sys.exit(1)
for sub, label in (("harbor_release", "holdout_harbor"), ("deep_release", "holdout_deep")):
    s = root / "holdout_release" / sub / "matrix_summary.json"
    d = json.loads(s.read_text())
    if not d.get("passed"):
        print(f"FAIL {label}")
        sys.exit(1)
    worst = max((sc["results"]["cep95_m"], name) for name, sc in d["scenarios"].items())
    print(f"PASS {label} worst_cep95={worst[0]:.3f}m ({worst[1]})")
print(f"VALIDATION_DAY_COMPLETE {root}")
PY

log "VALIDATION_DAY_DONE ${OUT}"
