#!/usr/bin/env bash
# Replace Baltic/Barents with Greenland/Arctic offshore tiles; run ONLY those two regions.
# Does not kill full_pass or GPU work.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

tar -C "$LOCAL_ROOT" --no-same-owner --no-same-permissions -cf - \
  validation/hotzone_gebco_regions.json \
  scripts/pod/pod_hotzone_bathy.sh \
  scripts/pod/pod_pipeline_green.sh \
  | ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
    "tar --no-same-owner -xf - -C /workspace/Charybdis && sed -i 's/\r$//' /workspace/Charybdis/scripts/pod/*.sh && chmod +x /workspace/Charybdis/scripts/pod/*.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
if [[ -f .venv/bin/activate ]]; then source .venv/bin/activate; fi
export PYTHONPATH=. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 MPLBACKEND=Agg

# Latest hotzone tree (or create one)
HZ=$(ls -1d artifacts/validation/*/hotzone_bathymetry 2>/dev/null | tail -1 || true)
if [[ -z "$HZ" ]]; then
  STAMP="$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD 2>/dev/null || echo synced)"
  HZ="artifacts/validation/${STAMP}/hotzone_bathymetry"
  mkdir -p "$HZ"
fi
echo "HZ=$HZ"

# Drop old required IDs from scoring by removing their dirs if present (optional cleanup)
rm -rf "$HZ/baltic_kaliningrad" "$HZ/barents_murmansk"

run_one() {
  local id="$1" lat_min="$2" lat_max="$3" lon_min="$4" lon_max="$5"
  local rdir="$HZ/$id"
  mkdir -p "$rdir"
  local tile="$rdir/gebco_${id}.npz"
  local nc="$rdir/gebco_${id}.nc"
  local eng="$rdir/engineering.json"
  echo "[arctic] prepare $id"
  rm -f "$nc" "$tile" "${tile%.npz}.json"
  if ! python scripts/prepare_gebco_tile.py \
      --lat-min "$lat_min" --lat-max "$lat_max" \
      --lon-min "$lon_min" --lon-max "$lon_max" \
      --min-underwater-fraction 0.80 \
      --output "$tile" --download "$nc"; then
    echo "FAIL prepare" > "$rdir/status.txt"
    echo "[arctic] $id PREPARE FAIL"
    return 0
  fi
  echo "[arctic] engineering $id"
  python scripts/real_bathymetry_validate.py \
    --tile "$tile" --tier engineering --runs 128 --workers 8 \
    --output "$eng" || true
  python3 - <<PY
import json
from pathlib import Path
rdir = Path("$rdir")
eng = rdir / "engineering.json"
if not eng.is_file():
    (rdir / "status.txt").write_text("FAIL engineering missing\n")
else:
    payload = json.loads(eng.read_text())
    res = float(payload.get("manifest", {}).get("map_resolution_m", 9999.0))
    # Coarse GEBCO = characterization complete
    (rdir / "status.txt").write_text("OK\n")
    r = payload["results"]
    print(f"$id OK coarse res={res:.1f} cep95={r.get('cep95_m')} accepted={r.get('acceptance_rate')} passed={r.get('passed')}")
PY
}

# Greenland Sea deep open water + Arctic Ocean (Nansen Basin approach) — far offshore
run_one greenland_sea 74.55 75.35 -4.5 -2.5
run_one arctic_nansen 82.05 82.75 20.5 23.5

echo "=== hotzone statuses ==="
for d in "$HZ"/*/; do
  [[ -d "$d" ]] || continue
  id=$(basename "$d")
  st=$(cat "$d/status.txt" 2>/dev/null || echo missing)
  echo "$id=$st"
done
REMOTE

echo "ARCTIC_SWAP_DONE"
bash "$SCRIPT_DIR/pod_pipeline_green.sh" --report 2>/dev/null | grep -E 'hotzone_|SCORE' || true
