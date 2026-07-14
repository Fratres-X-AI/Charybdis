#!/usr/bin/env bash
# High-resolution public NOAA bathymetry candidate validation (pod only).
set -euo pipefail

REPO=/workspace/Charybdis
cd "$REPO"

LOG=/tmp/pod_highres_bathy.log
: >"$LOG"
ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

source .venv/bin/activate
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export MPLBACKEND=Agg

STAMP=$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD 2>/dev/null || echo synced)
OUT="artifacts/validation/${STAMP}/highres_bathymetry"
mkdir -p "$OUT"

TILE="${OUT}/noaa_monterey_bay_p080.npz"
NC="${OUT}/noaa_monterey_bay_p080.nc"

log "prepare NOAA/NCEI Monterey Bay P080 DEM"
rm -f "$NC" "$TILE" "${TILE%.npz}.json"
python scripts/prepare_noaa_dem_tile.py \
  --output "$TILE" \
  --download "$NC" 2>&1 | tee -a "$LOG"

log "engineering high-resolution real-bathymetry characterization"
python scripts/real_bathymetry_validate.py \
  --tile "$TILE" \
  --tier engineering \
  --runs 64 \
  --workers 31 \
  --require-integration-grade-map \
  --output "${OUT}/engineering.json" 2>&1 | tee -a "$LOG"

log "release high-resolution real-bathymetry characterization"
set +e
python scripts/real_bathymetry_validate.py \
  --tile "$TILE" \
  --tier release \
  --runs 256 \
  --workers 31 \
  --require-integration-grade-map \
  --output "${OUT}/release.json" 2>&1 | tee -a "$LOG"
release_rc=$?
set -e

python3 - <<'PY' | tee -a "$LOG"
import json
from pathlib import Path

root = sorted(
    Path("artifacts/validation").glob("*/highres_bathymetry"),
    key=lambda p: p.stat().st_mtime,
)[-1]
for name in ("engineering", "release"):
    payload = json.loads((root / f"{name}.json").read_text())
    manifest = payload["manifest"]
    results = payload["results"]
    print(
        f"{name}: pass={results['passed']} "
        f"resolution={manifest['map_resolution_m']:.3f}m "
        f"class={manifest['resolution_class']} "
        f"accepted={results['acceptance_rate']:.3f} "
        f"cep95={results['cep95_m']}"
    )
print(f"HIGHRES_BATHY_COMPLETE {root}")
PY

sha256sum "$TILE" "$NC" "${OUT}/"*.json "${OUT}/"*.md > "${OUT}/SHA256SUMS"
log "HIGHRES_BATHY_COMPLETE ${OUT} release_rc=${release_rc:-0}"
