#!/usr/bin/env bash
set -euo pipefail

HOST="root@64.247.206.218"
PORT="14049"
KEY="${HOME}/.ssh/id_ed25519"
LOCAL="$(cd "$(dirname "$0")/../.." && pwd)"

sed -i 's/\r$//' "${LOCAL}/scripts/pod/pod_hybrid_phase2.sh"

scp -P "$PORT" -i "$KEY" -o StrictHostKeyChecking=no \
  "${LOCAL}/scripts/pod/pod_hybrid_phase2.sh" \
  "${HOST}:/workspace/Charybdis/scripts/pod/"

ssh -p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no "$HOST" 'bash -s' <<'REMOTE'
set -euo pipefail
sed -i 's/\r$//' /workspace/Charybdis/scripts/pod/pod_hybrid_phase2.sh
chmod +x /workspace/Charybdis/scripts/pod/pod_hybrid_phase2.sh
REMOTE

bash "$(dirname "$0")/launch_phase2.sh"
