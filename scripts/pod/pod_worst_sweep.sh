#!/usr/bin/env bash
# Max-confidence sweep on historically worst scenarios (512 runs, 31 workers).
set -euo pipefail
REPO=/workspace/Charybdis
cd "$REPO"
LOG=/tmp/pod_worst_sweep.log
: >"$LOG"
ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

STAMP=$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD 2>/dev/null || echo synced)-$$
OUT="artifacts/validation/${STAMP}/worst_sweep"
log "=== 512-run worst-scenario sweep -> ${OUT} ==="

HARBOR_SCENARIOS=(sparse_outlier_bathymetry repeated_mode_transitions)
DEEP_SCENARIOS=(deep_midwater deep_long_blackout deep_sparse_bathymetry)

(
  python scripts/hybrid_validate_matrix.py \
    --tier engineering --runs 512 --workers 31 --allow-dirty \
    --scenarios "${HARBOR_SCENARIOS[@]}" \
    --output-dir "${OUT}/harbor_worst" 2>&1 | tee "/tmp/pod_worst_harbor.log"
) &
pid_h=$!
(
  python scripts/hybrid_validate_deep_matrix.py \
    --tier engineering --runs 512 --workers 31 --allow-dirty \
    --scenarios "${DEEP_SCENARIOS[@]}" \
    --output-dir "${OUT}/deep_worst" 2>&1 | tee "/tmp/pod_worst_deep.log"
) &
pid_d=$!
wait "$pid_h" "$pid_d"

python - <<'PY' | tee -a "$LOG"
import json
from pathlib import Path
root = sorted(Path("artifacts/validation").glob("*/worst_sweep"), key=lambda p: p.stat().st_mtime)[-1]
for sub in ("harbor_worst", "deep_worst"):
    d = json.loads((root / sub / "matrix_summary.json").read_text())
    for name, sc in sorted(d["scenarios"].items()):
        r = sc["results"]
        print(f"{sub} {name}: cep95={r['cep95_m']:.4f} upper={sc['assessment']['checks']['cep95_upper_m']['observed']:.4f} passed={sc['assessment']['passed']}")
PY
log "WORST_SWEEP_COMPLETE ${OUT}"
