#!/usr/bin/env bash
# Highres-only pod kick (fast iteration on placement/matcher tuning).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

echo "[kick-highres] sync -> ${POD_NAME}"
bash "$LOCAL_ROOT/scripts/pod/sync_pod.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
for f in scripts/pod/*.sh; do sed -i 's/\r$//' "$f"; chmod +x "$f"; done
pkill -f 'pod_highres_bathy.sh' 2>/dev/null || true
nohup bash -c '
  set -euo pipefail
  cd /workspace/Charybdis
  source .venv/bin/activate
  export PYTHONPATH=.
  bash scripts/pod/pod_highres_bathy.sh
' > /tmp/pod_highres_bathy_stdout.log 2>&1 &
sleep 1
echo kicked_highres
pgrep -af 'pod_highres_bathy|real_bathymetry|prepare_noaa' || echo pending
tail -3 /tmp/pod_highres_bathy_stdout.log 2>/dev/null || true
REMOTE
