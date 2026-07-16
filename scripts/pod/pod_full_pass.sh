#!/usr/bin/env bash
# Full validation burst on pod: mission + highres + holdout harbor + holdout deep.
set -euo pipefail

REPO=/workspace/Charybdis
cd "$REPO"
LOG=/tmp/pod_full_pass.log
: >"$LOG"
ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export MPLBACKEND=Agg

WORKERS=31
STAMP="$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD 2>/dev/null || echo synced)"
OUT="artifacts/validation/${STAMP}/full_pass"
mkdir -p "$OUT"

log "=== 1/4 mission engineering 256 ==="
python scripts/hybrid_validate_mission_matrix.py \
  --tier engineering --runs 256 --workers "${WORKERS}" --allow-dirty \
  --output-dir "${OUT}/mission_engineering" 2>&1 | tee -a "$LOG"

log "=== 2/4 highres eng+release ==="
bash scripts/pod/pod_highres_bathy.sh 2>&1 | tee -a "$LOG"

log "=== 3/4 holdout harbor release 256 ==="
python scripts/hybrid_validate_matrix.py \
  --tier release --runs 256 --workers "${WORKERS}" \
  --seeds validation/seeds_holdout_v1.txt --allow-dirty \
  --output-dir "${OUT}/holdout_harbor" 2>&1 | tee -a "$LOG"

log "=== 4/4 holdout deep release 256 ==="
python scripts/hybrid_validate_deep_matrix.py \
  --tier release --runs 256 --workers "${WORKERS}" \
  --seeds validation/seeds_holdout_v1.txt --allow-dirty \
  --output-dir "${OUT}/holdout_deep" 2>&1 | tee -a "$LOG"

python3 - <<'PY' | tee -a "$LOG"
import json, sys
from pathlib import Path

root = sorted(Path("artifacts/validation").glob("*/full_pass"), key=lambda p: p.stat().st_mtime)[-1]
checks = [
    ("mission", root / "mission_engineering" / "matrix_summary.json"),
    ("holdout_harbor", root / "holdout_harbor" / "matrix_summary.json"),
    ("holdout_deep", root / "holdout_deep" / "matrix_summary.json"),
]
highres = sorted(Path("artifacts/validation").glob("*/highres_bathymetry/release.json"), key=lambda p: p.stat().st_mtime)[-1]
hr = json.loads(highres.read_text())
print(f"highres pass={hr['results']['passed']} cep95={hr['results']['cep95_m']:.3f}")
if not hr["results"]["passed"]:
    sys.exit(1)
for label, path in checks:
    data = json.loads(path.read_text())
    print(f"{label} pass={data['passed']}")
    if not data["passed"]:
        for name, sc in data["scenarios"].items():
            if not sc["assessment"]["passed"]:
                r = sc["results"]
                print(f"  FAIL {name} cep95={r.get('cep95_m')} gps_jump={r.get('gps_reacquisition_jump_cep95_m')}")
        sys.exit(1)
print(f"FULL_PASS_COMPLETE {root}")
PY

log "FULL_PASS_DONE ${OUT}"
