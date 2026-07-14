#!/usr/bin/env bash
set -euo pipefail
HOST=root@213.173.107.32
PORT=37613
KEY="${HOME}/.ssh/id_ed25519"
LOCAL_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

bash "$LOCAL_ROOT/scripts/pod/sync_pod_bronze.sh"
ssh -o StrictHostKeyChecking=no -p "$PORT" -i "$KEY" "$HOST" <<'REMOTE'
cd /workspace/Charybdis
nohup bash scripts/pod/pod_bronze_beach.sh > /tmp/pod_bronze_beach_stdout.log 2>&1 &
echo "beach_pid=$!"
REMOTE
