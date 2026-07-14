#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOST=root@213.173.107.32
PORT=37613
KEY="${HOME}/.ssh/id_ed25519"

bash "$SCRIPT_DIR/sync_pod_bronze.sh"

ssh -o StrictHostKeyChecking=no -p "$PORT" -i "$KEY" "$HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
sed -i 's/\r$//' scripts/pod/pod_bronze_military.sh
chmod +x scripts/pod/pod_bronze_military.sh
nohup bash scripts/pod/pod_bronze_military.sh > /tmp/pod_bronze_military.log 2>&1 &
echo "military_pid=$!"
REMOTE
