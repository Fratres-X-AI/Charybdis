#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/pod/pod_env.sh
source "$SCRIPT_DIR/pod_env.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" bash -s <<'REMOTE'
echo "TIME=$(date -u +%H:%M:%SZ)"
pgrep -af pod_validation || echo "no_validation_proc"
pgrep -c -f hybrid_validate 2>/dev/null || echo "0_validate"
pgrep -c -f real_bathymetry_validate 2>/dev/null || echo "0_highres"
tail -6 /tmp/pod_validation_day_stdout.log 2>/dev/null || echo "no_stdout_log"
tail -4 /tmp/pod_validation_day.log 2>/dev/null || echo "no_main_log"
REMOTE
