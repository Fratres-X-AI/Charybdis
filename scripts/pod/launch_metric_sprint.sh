#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

bash "$LOCAL_ROOT/scripts/pod/sync_pod.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
bash scripts/pod/pod_bootstrap_venv.sh
for f in scripts/pod/pod_metric_sprint.sh scripts/pod/pod_highres_bathy.sh scripts/pod/pod_integration_grade.sh; do
  sed -i 's/\r$//' "$f"
  chmod +x "$f"
done
nohup bash scripts/pod/pod_metric_sprint.sh > /tmp/pod_metric_sprint_stdout.log 2>&1 &
echo sprint_pid=$!
REMOTE
