#!/usr/bin/env bash
# GEBCO characterization on global hot-zone bboxes (Hormuz, Russia-adjacent, etc.).
# Coarse public tiles — NOT integration-grade; documents matcher behavior by region.
set -euo pipefail

REPO=/workspace/Charybdis
cd "$REPO"
LOG=/tmp/pod_hotzone_bathy.log
: >"$LOG"
ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
export PYTHONPATH=.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 MPLBACKEND=Agg

WORKERS="${HOTZONE_WORKERS:-8}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD 2>/dev/null || echo synced)"
OUT="artifacts/validation/${STAMP}/hotzone_bathymetry"
mkdir -p "$OUT"
REGIONS="${REPO}/validation/hotzone_gebco_regions.json"

log "HOTZONE_BATHY_START workers=${WORKERS} out=${OUT}"

run_region() {
  local id="$1" label="$2" lat_min="$3" lat_max="$4" lon_min="$5" lon_max="$6" tier="$7"
  local rdir="${OUT}/${id}"
  mkdir -p "$rdir"
  local tile="${rdir}/gebco_${id}.npz"
  local nc="${rdir}/gebco_${id}.nc"
  local eng="${rdir}/engineering.json"
  local rel="${rdir}/release.json"

  log "region ${id} prepare (${label})"
  rm -f "$nc" "$tile" "${tile%.npz}.json"
  if ! python scripts/prepare_gebco_tile.py \
    --lat-min "$lat_min" --lat-max "$lat_max" \
    --lon-min "$lon_min" --lon-max "$lon_max" \
    --min-underwater-fraction 0.80 \
    --output "$tile" --download "$nc" >>"$LOG" 2>&1; then
    log "region ${id} SKIP prepare failed"
    echo "FAIL prepare" > "${rdir}/status.txt"
    return 0
  fi

  log "region ${id} engineering @ ${WORKERS}w"
  python scripts/real_bathymetry_validate.py \
    --tile "$tile" --tier engineering --runs 256 --workers "$WORKERS" \
    --output "$eng" >>"$LOG" 2>&1 || true

  if [[ "$tier" == "release" ]]; then
    res_m=$(python3 - <<PY
import json
from pathlib import Path
meta = json.loads(Path("${tile}".replace(".npz", ".json")).read_text())
print(float(meta.get("resolution_m", 9999.0)))
PY
)
    if python3 - <<PY
res = float("${res_m}")
import sys
sys.exit(0 if res <= 100.0 else 1)
PY
    then
      log "region ${id} release @ ${WORKERS}w"
      python scripts/real_bathymetry_validate.py \
        --tile "$tile" --tier release --runs 256 --workers "$WORKERS" \
        --output "$rel" >>"$LOG" 2>&1 || true
    else
      log "region ${id} skip release (coarse ${res_m}m — engineering only)"
    fi
  fi

  python3 - <<PY >>"$LOG" 2>&1
import json
from pathlib import Path
rdir = Path("${rdir}")
for name in ("engineering", "release"):
    path = rdir / f"{name}.json"
    if not path.is_file():
        continue
    p = json.loads(path.read_text())
    r = p["results"]
    m = p["manifest"]
    print(
        f"${id} {name}: pass={r['passed']} class={m['resolution_class']} "
        f"res={m['map_resolution_m']:.1f}m cep95={r['cep95_m']:.1f} "
        f"accepted={r['acceptance_rate']:.3f}"
    )
PY
  # Coarse public GEBCO (~450 m) is characterization-only — complete run == OK.
  # Fine maps still require engineering pass.
  python3 - <<PY
import json
from pathlib import Path

rdir = Path("${rdir}")
eng = rdir / "engineering.json"
status_path = rdir / "status.txt"
if not eng.is_file():
    status_path.write_text("FAIL engineering missing\n")
    raise SystemExit(0)
payload = json.loads(eng.read_text())
res = float(payload.get("manifest", {}).get("map_resolution_m", 9999.0))
passed = bool(payload["results"]["passed"])
if res > 100.0:
    status_path.write_text("OK\n")
    print(f"${id} coarse characterization complete res={res:.1f}m passed={passed}")
elif passed:
    status_path.write_text("OK\n")
else:
    status_path.write_text("FAIL engineering\n")
PY
  log "region ${id} done"
}

python3 - <<'PY' | while IFS=$'\t' read -r id label lat_min lat_max lon_min lon_max tier; do
import json
from pathlib import Path
regions = json.loads(Path("validation/hotzone_gebco_regions.json").read_text())
for r in regions:
    print(
        f"{r['id']}\t{r['label']}\t{r['lat_min']}\t{r['lat_max']}\t"
        f"{r['lon_min']}\t{r['lon_max']}\t{r['tier']}"
    )
PY
  run_region "$id" "$label" "$lat_min" "$lat_max" "$lon_min" "$lon_max" "$tier" &
done
wait

python3 - <<'PY' | tee -a "$LOG"
import json
from pathlib import Path

root = sorted(Path("artifacts/validation").glob("*/hotzone_bathymetry"))[-1]
print(f"HOTZONE_SUMMARY {root}")
for region_dir in sorted(root.iterdir()):
    if not region_dir.is_dir():
        continue
    status = (region_dir / "status.txt").read_text().strip() if (region_dir / "status.txt").exists() else "?"
    best = None
    for name in ("release", "engineering"):
        path = region_dir / f"{name}.json"
        if not path.is_file():
            continue
        payload = json.loads(path.read_text())
        r = payload["results"]
        best = f"{name} pass={r['passed']} cep95={r['cep95_m']:.1f}m"
        break
    print(f"  {region_dir.name}: {status} {best or 'no json'}")
PY

(
  cd "$OUT"
  find . -type f \( -name '*.json' -o -name '*.npz' -o -name '*.txt' \) -print0 2>/dev/null \
    | xargs -0 sha256sum > SHA256SUMS 2>/dev/null || true
)
log "HOTZONE_BATHY_COMPLETE ${OUT}"
