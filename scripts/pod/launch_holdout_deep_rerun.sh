#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/pod/pod_env.sh
source "$SCRIPT_DIR/pod_env.sh"

echo "=== sync ==="
bash "$SCRIPT_DIR/sync_pod.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" bash -s <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
for f in scripts/pod/*.sh; do sed -i 's/\r$//' "$f"; chmod +x "$f"; done
nohup bash scripts/pod/pod_holdout_deep_rerun.sh > /tmp/pod_holdout_deep_rerun_stdout.log 2>&1 &
echo "launched pid=$! log=/tmp/pod_holdout_deep_rerun_stdout.log"
REMOTE
