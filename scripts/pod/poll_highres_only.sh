#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
echo "TIME=$(date -u +%H:%M:%SZ) sha=$(git rev-parse --short HEAD)"
pgrep -af 'pod_highres|real_bathymetry|prepare_noaa' || echo idle
echo "--- stdout ---"
tail -12 /tmp/pod_highres_bathy_stdout.log 2>/dev/null || true
echo "--- log ---"
tail -8 /tmp/pod_highres_bathy.log 2>/dev/null || true
d=$(ls -td artifacts/validation/*/highres_bathymetry 2>/dev/null | head -1)
if [[ -n "${d:-}" && -f "$d/release.json" ]]; then
  python3 -c "import json; d=json.load(open('$d/release.json')); r=d['results']; print('RELEASE', r['passed'], r['acceptance_rate'], r['cep95_m'], r['status_counts'])"
fi
if [[ -n "${d:-}" && -f "$d/engineering.json" ]]; then
  python3 -c "import json; d=json.load(open('$d/engineering.json')); r=d['results']; print('ENGINEERING', r['passed'], r['acceptance_rate'], r['cep95_m'], r['status_counts'])"
fi
REMOTE
