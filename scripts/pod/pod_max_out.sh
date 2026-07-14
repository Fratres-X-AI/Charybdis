#!/usr/bin/env bash
# Max CPU utilization: 4x31-worker validation lanes + NOAA high-res release.
set -euo pipefail
REPO=/workspace/Charybdis
cd "$REPO"
LOG=/tmp/pod_max_out.log
: >"$LOG"
ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export MPLBACKEND=Agg

STAMP=$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD 2>/dev/null || echo synced)-$$
OUT="artifacts/validation/${STAMP}/max_out"
mkdir -p "$OUT"
log "MAX_OUT_START stamp=${STAMP} cpus=$(nproc)"

log "lane1 harbor release 256@31"
(
  python scripts/hybrid_validate_matrix.py \
    --tier release --runs 256 --workers 31 --allow-dirty \
    --output-dir "${OUT}/harbor_release" 2>&1 | tee "/tmp/pod_max_harbor_rel.log"
) &
pid_hr=$!

log "lane2 deep release 256@31"
(
  python scripts/hybrid_validate_deep_matrix.py \
    --tier release --runs 256 --workers 31 --allow-dirty \
    --output-dir "${OUT}/deep_release" 2>&1 | tee "/tmp/pod_max_deep_rel.log"
) &
pid_dr=$!

HARBOR_SCENARIOS=(sparse_outlier_bathymetry repeated_mode_transitions)
DEEP_SCENARIOS=(deep_midwater deep_long_blackout deep_sparse_bathymetry)

log "lane3 harbor worst 512@31"
(
  python scripts/hybrid_validate_matrix.py \
    --tier engineering --runs 512 --workers 31 --allow-dirty \
    --scenarios "${HARBOR_SCENARIOS[@]}" \
    --output-dir "${OUT}/harbor_worst" 2>&1 | tee "/tmp/pod_max_harbor_worst.log"
) &
pid_hw=$!

log "lane4 deep worst 512@31"
(
  python scripts/hybrid_validate_deep_matrix.py \
    --tier engineering --runs 512 --workers 31 --allow-dirty \
    --scenarios "${DEEP_SCENARIOS[@]}" \
    --output-dir "${OUT}/deep_worst" 2>&1 | tee "/tmp/pod_max_deep_worst.log"
) &
pid_dw=$!

TILE=$(ls -t artifacts/validation/*/highres_bathymetry/noaa_monterey_bay_p080.npz 2>/dev/null | head -1 || true)
pid_hb=""
if [[ -n "${TILE}" && -f "${TILE}" ]]; then
  log "lane5 NOAA highres release 256@31 tile=${TILE}"
  (
    set +e
    python scripts/real_bathymetry_validate.py \
      --tile "${TILE}" \
      --tier release \
      --runs 256 \
      --workers 31 \
      --require-integration-grade-map \
      --output "${OUT}/highres_release.json" 2>&1 | tee "/tmp/pod_max_highres.log"
    echo highres_rc=$? >> /tmp/pod_max_highres.log
    set -e
  ) &
  pid_hb=$!
else
  log "lane5 skip NOAA highres (no tile on pod)"
fi

wait "$pid_hr" "$pid_dr" "$pid_hw" "$pid_dw"
[[ -n "$pid_hb" ]] && wait "$pid_hb" || true

python3 - <<'PY' | tee -a "$LOG"
import json
from pathlib import Path

root = sorted(Path("artifacts/validation").glob("*/max_out"), key=lambda p: p.stat().st_mtime)[-1]
for sub, label in (
    ("harbor_release", "harbor_rel"),
    ("deep_release", "deep_rel"),
    ("harbor_worst", "harbor_worst"),
    ("deep_worst", "deep_worst"),
):
    summary = root / sub / "matrix_summary.json"
    if not summary.exists():
        print(f"MISSING {label}")
        continue
    data = json.loads(summary.read_text())
    worst = max((sc["results"]["cep95_m"], name) for name, sc in data["scenarios"].items())
    print(f"{label}: pass={data['passed']} worst_cep95={worst[0]:.3f}m ({worst[1]})")
highres = root / "highres_release.json"
if highres.exists():
    payload = json.loads(highres.read_text())
    r = payload["results"]
    print(
        f"highres: pass={r['passed']} accepted={r['acceptance_rate']:.3f} "
        f"cep95={r['cep95_m']} class={payload['manifest']['resolution_class']}"
    )
print(f"MAX_OUT_COMPLETE {root}")
PY

log "MAX_OUT_COMPLETE ${OUT}"
