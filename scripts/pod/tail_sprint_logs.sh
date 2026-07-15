#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
echo === sprint ===
tail -20 /tmp/pod_hour_sprint_stdout.log 2>/dev/null || true
echo === highres ===
tail -10 /tmp/pod_highres_bathy.log 2>/dev/null || true
echo === integration ===
tail -15 /tmp/pod_integration_grade_stdout.log 2>/dev/null || true
tail -15 /tmp/pod_integration_grade.log 2>/dev/null || true
pgrep -af pod_hour_sprint || echo no_sprint
pgrep -af pod_integration || echo no_integration
pgrep -c -f hybrid_validate || echo 0
REMOTE
