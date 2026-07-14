#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
echo "TIME=$(date -u +%H:%M:%SZ)"
pgrep -af "pod_highres_bathy|prepare_noaa_dem_tile|real_bathymetry_validate" || echo "no_highres_proc"
echo "--- stdout ---"
tail -10 /tmp/pod_highres_bathy_stdout.log 2>/dev/null || true
echo "--- log ---"
tail -12 /tmp/pod_highres_bathy.log 2>/dev/null || true
latest=$(ls -td artifacts/validation/*/highres_bathymetry 2>/dev/null | head -1 || true)
if [[ -n "$latest" ]]; then
  echo "latest=$latest"
  if [[ -f "$latest/release.json" ]]; then
    python3 - "$latest/release.json" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1]))
manifest = payload["manifest"]
results = payload["results"]
print(
    "release_summary "
    f"passed={results['passed']} "
    f"resolution={manifest['map_resolution_m']:.3f}m "
    f"class={manifest['resolution_class']} "
    f"acceptance={results['acceptance_rate']:.3f} "
    f"cep95={results['cep95_m']}"
)
PY
  fi
fi
REMOTE
