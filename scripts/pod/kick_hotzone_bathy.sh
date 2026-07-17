#!/usr/bin/env bash
# Deploy hot-zone GEBCO suite and launch on active pod (CPU-only, parallel regions).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

echo "=== KICK HOTZONE BATHY pod=${POD_NAME} ==="

tar -C "$LOCAL_ROOT" --no-same-owner --no-same-permissions -cf - \
  validation/hotzone_gebco_regions.json \
  scripts/prepare_gebco_tile.py \
  scripts/pod/pod_hotzone_bathy.sh \
  2>/dev/null | ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
  "tar --no-same-owner -xf - -C /workspace/Charybdis && chmod +x /workspace/Charybdis/scripts/pod/pod_hotzone_bathy.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
for f in scripts/pod/pod_hotzone_bathy.sh; do sed -i 's/\r$//' "$f"; chmod +x "$f"; done
source .venv/bin/activate

if pgrep -f pod_hotzone_bathy >/dev/null 2>&1; then
  echo "hotzone already running"
else
  echo "[launch] hotzone GEBCO characterization (8 regions parallel)"
  nohup bash scripts/pod/pod_hotzone_bathy.sh > /tmp/pod_hotzone_bathy_stdout.log 2>&1 &
fi
sleep 3
pgrep -af 'pod_hotzone_bathy|prepare_gebco|real_bathymetry.*hotzone' | head -12 || true
tail -5 /tmp/pod_hotzone_bathy.log 2>/dev/null || tail -5 /tmp/pod_hotzone_bathy_stdout.log 2>/dev/null || true
REMOTE

echo "KICK_HOTZONE_BATHY_DONE"
