#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/pod/pod_env.sh
source "$SCRIPT_DIR/pod_env.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" bash -s <<'REMOTE'
echo "TIME=$(date -u +%H:%M:%SZ)"
pgrep -af pod_holdout_deep || echo "no_proc"
pgrep -c -f hybrid_validate_deep || echo "0"
tail -8 /tmp/pod_holdout_deep_rerun_stdout.log 2>/dev/null || echo "no_log"
tail -4 /tmp/pod_holdout_deep_rerun.log 2>/dev/null || true
REMOTE
