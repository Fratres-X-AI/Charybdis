#!/usr/bin/env bash
# Non-blocking pod kick: sync, bootstrap, sprint — returns immediately.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

echo "[kick] sync -> ${POD_NAME} (${POD_HOST}:${POD_PORT})"
bash "$LOCAL_ROOT/scripts/pod/sync_pod.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
for f in scripts/pod/*.sh; do sed -i 's/\r$//' "$f"; chmod +x "$f"; done

# Kill any stale bootstrap/sprint from a blocking prior launch.
pkill -f 'pod_metric_sprint.sh' 2>/dev/null || true

nohup bash -c '
  set -euo pipefail
  cd /workspace/Charybdis
  echo "[kick] bootstrap start $(date -u +%H:%M:%SZ)" >> /tmp/pod_metric_sprint_stdout.log
  bash scripts/pod/pod_bootstrap_venv.sh >> /tmp/pod_metric_sprint_stdout.log 2>&1
  echo "[kick] sprint start $(date -u +%H:%M:%SZ)" >> /tmp/pod_metric_sprint_stdout.log
  bash scripts/pod/pod_metric_sprint.sh >> /tmp/pod_metric_sprint_stdout.log 2>&1
  echo "[kick] done $(date -u +%H:%M:%SZ)" >> /tmp/pod_metric_sprint_stdout.log
' > /dev/null 2>&1 &

sleep 1
echo "kicked pid=$!"
echo "--- tail stdout ---"
tail -5 /tmp/pod_metric_sprint_stdout.log 2>/dev/null || echo "(log starting)"
pgrep -af 'pod_metric_sprint|pod_bootstrap|real_bathymetry|hybrid_validate' || echo "procs pending"
REMOTE

echo "[kick] detached on pod — poll with: bash scripts/pod/poll_metric_sprint.sh"
