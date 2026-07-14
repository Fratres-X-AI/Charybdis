#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOST=root@195.26.233.70
PORT=55580
KEY="${HOME}/.ssh/id_ed25519"
ROOT="${1:-artifacts/validation/20260714T132210Z-ad7fa3e}"

bash "$SCRIPT_DIR/sync_pod_a100.sh"

ssh -p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no "$HOST" <<REMOTE
set -euo pipefail
cd /workspace/Charybdis
pkill -f pod_a100_finish || true
pkill -f prepare_gebco_tile || true
sleep 2
sed -i 's/\r$//' scripts/pod/pod_a100_resume.sh
chmod +x scripts/pod/pod_a100_resume.sh
nohup bash scripts/pod/pod_a100_resume.sh "${ROOT}" >> /tmp/pod_a100_finish.log 2>&1 &
echo "resume_pid=\$! root=${ROOT}"
REMOTE
