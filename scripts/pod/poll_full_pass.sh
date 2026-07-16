#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/pod/pod_env.sh
source "$SCRIPT_DIR/pod_env.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" bash -s <<'REMOTE'
echo "TIME=$(date -u +%H:%M:%SZ)"
pgrep -af pod_full_pass || echo "no_proc"
pgrep -c -f hybrid_validate 2>/dev/null || echo "0"
tail -10 /tmp/pod_full_pass_stdout.log 2>/dev/null || echo "no_log"
tail -3 /tmp/pod_full_pass.log 2>/dev/null || true
REMOTE
