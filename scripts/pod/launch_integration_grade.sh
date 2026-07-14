#!/usr/bin/env bash
set -euo pipefail
LOCAL_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
bash "$LOCAL_ROOT/scripts/pod/sync_pod_bronze.sh"
HOST=root@213.173.107.32
PORT=37613
KEY="${HOME}/.ssh/id_ed25519"
ssh -o StrictHostKeyChecking=no -p "$PORT" -i "$KEY" "$HOST" <<'REMOTE'
cd /workspace/Charybdis
nohup bash scripts/pod/pod_integration_grade.sh > /tmp/pod_integration_grade_stdout.log 2>&1 &
echo "integration_pid=$!"
REMOTE
