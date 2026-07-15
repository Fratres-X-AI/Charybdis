#!/usr/bin/env bash
# Non-blocking max CPU kick: sync, bootstrap, pod_max_out — returns immediately.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

echo "[kick_max] sync -> ${POD_NAME} (${POD_HOST}:${POD_PORT})"
bash "$LOCAL_ROOT/scripts/pod/sync_pod.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
for f in scripts/pod/*.sh; do sed -i 's/\r$//' "$f"; chmod +x "$f"; done

pkill -f 'pod_max_out.sh' 2>/dev/null || true

nohup bash -c '
  set -euo pipefail
  cd /workspace/Charybdis
  echo "[kick_max] bootstrap start $(date -u +%H:%M:%SZ)" >> /tmp/pod_max_out_stdout.log
  bash scripts/pod/pod_bootstrap_venv.sh >> /tmp/pod_max_out_stdout.log 2>&1
  echo "[kick_max] max_out start $(date -u +%H:%M:%SZ)" >> /tmp/pod_max_out_stdout.log
  bash scripts/pod/pod_max_out.sh >> /tmp/pod_max_out_stdout.log 2>&1
  echo "[kick_max] done $(date -u +%H:%M:%SZ)" >> /tmp/pod_max_out_stdout.log
' > /dev/null 2>&1 &

sleep 1
echo "kicked_max pid=$!"
tail -5 /tmp/pod_max_out_stdout.log 2>/dev/null || echo "(log starting)"
pgrep -af 'pod_max_out|hybrid_validate|real_bathymetry' || echo "procs pending"
REMOTE

echo "[kick_max] detached — poll: bash scripts/pod/poll_pod_max.sh"
