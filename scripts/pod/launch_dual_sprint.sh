#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
bash "$SCRIPT_DIR/sync_pod_dual.sh"
ssh -p 30511 -i "${HOME}/.ssh/id_ed25519" -o StrictHostKeyChecking=no root@157.157.221.29 \
  'nohup bash /workspace/Charybdis/scripts/pod/pod_dual_sprint.sh > /tmp/pod_dual_sprint.out 2>&1 &'
echo "launched dual sprint on impossible_bronze_bedbug"
