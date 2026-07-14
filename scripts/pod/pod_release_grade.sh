#!/usr/bin/env bash
# Release-tier validation — harbor+deep 256 runs @ 31 workers each (pod only).
set -euo pipefail
REPO=/workspace/Charybdis
cd "$REPO"
LOG=/tmp/pod_release_grade.log
: >"$LOG"
ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export MPLBACKEND=Agg

STAMP=$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD 2>/dev/null || echo synced)-$$
OUT="artifacts/validation/${STAMP}/release_grade"
log "=== Release tier harbor+deep 256x @ 31+31 workers -> ${OUT} ==="
(
  python scripts/hybrid_validate_matrix.py \
    --tier release --runs 256 --workers 31 --allow-dirty \
    --output-dir "${OUT}/harbor_release" 2>&1 | tee "/tmp/pod_rel_harbor.log"
) &
pid_h=$!
(
  python scripts/hybrid_validate_deep_matrix.py \
    --tier release --runs 256 --workers 31 --allow-dirty \
    --output-dir "${OUT}/deep_release" 2>&1 | tee "/tmp/pod_rel_deep.log"
) &
pid_d=$!
wait "$pid_h" "$pid_d"
python - <<'PY' | tee -a "$LOG"
import json, sys
from pathlib import Path
root = sorted(Path("artifacts/validation").glob("*/release_grade"), key=lambda p: p.stat().st_mtime)[-1]
for sub, label in (("harbor_release", "harbor"), ("deep_release", "deep")):
    s = root / sub / "matrix_summary.json"
    d = json.loads(s.read_text())
    if not d.get("passed"):
        print(f"FAIL {label}")
        sys.exit(1)
    worst = max(
        (sc["results"]["cep95_m"], name)
        for name, sc in d["scenarios"].items()
    )
    print(f"PASS {label} worst_cep95={worst[0]:.3f}m ({worst[1]})")
PY
log "RELEASE_GRADE_COMPLETE ${OUT}"
