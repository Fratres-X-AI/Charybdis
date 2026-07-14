#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/pod/pod_env.sh
source "$SCRIPT_DIR/pod_env.sh"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

bash "$LOCAL_ROOT/scripts/pod/sync_pod.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
bash scripts/pod/pod_bootstrap_venv.sh
nohup bash scripts/pod/pod_integration_grade.sh > /tmp/pod_integration_grade_stdout.log 2>&1 &
echo "integration_pid=$!"
REMOTE
