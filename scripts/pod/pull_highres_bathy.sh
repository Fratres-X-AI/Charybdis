#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
DEST="$LOCAL_ROOT/artifacts/pod_highres_bathy_pull_${STAMP}"
mkdir -p "$DEST"

REMOTE_DIR=$(
  ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
    'ls -td /workspace/Charybdis/artifacts/validation/*/highres_bathymetry 2>/dev/null | head -1'
)

if [[ -z "$REMOTE_DIR" ]]; then
  echo "no remote highres_bathymetry artifact found" >&2
  exit 1
fi

scp -P "$POD_PORT" -i "$POD_KEY" -r "$POD_HOST:$REMOTE_DIR/"* "$DEST/"
mkdir -p "$DEST/logs"
for f in pod_highres_bathy.log pod_highres_bathy_stdout.log; do
  scp -P "$POD_PORT" -i "$POD_KEY" "$POD_HOST:/tmp/$f" "$DEST/logs/" 2>/dev/null || true
done

cat > "$DEST/README.md" <<EOF
# High-resolution bathymetry pull

- Pulled: ${STAMP} UTC
- Pod: ${POD_NAME} (${POD_HOST}:${POD_PORT})
- Remote artifact: ${REMOTE_DIR}
- Source: NOAA/NCEI Monterey Bay P080 bathymetric DEM
- Gate: scripts/real_bathymetry_validate.py --require-integration-grade-map

Logs are under \`logs/\`.
EOF

echo "PULL_COMPLETE dest=$DEST"
du -sh "$DEST" 2>/dev/null || true
