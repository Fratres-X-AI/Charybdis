#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
bash "$LOCAL_ROOT/scripts/pod/sync_pod.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
sed -i 's/\r$//' scripts/pod/pod_release_grade.sh
source .venv/bin/activate
nohup bash scripts/pod/pod_release_grade.sh > /tmp/pod_release_grade_stdout.log 2>&1 &
echo release_pid=$!
REMOTE
