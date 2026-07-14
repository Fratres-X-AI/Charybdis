#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOST=root@195.26.233.70
PORT=55580
KEY="${HOME}/.ssh/id_ed25519"

bash "$SCRIPT_DIR/sync_pod_a100.sh"

ssh -p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no "$HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
sed -i 's/\r$//' scripts/pod/pod_a100_finish.sh
chmod +x scripts/pod/pod_a100_finish.sh
nohup bash scripts/pod/pod_a100_finish.sh > /tmp/pod_a100_finish.log 2>&1 &
echo "finish_pid=$!"
REMOTE
