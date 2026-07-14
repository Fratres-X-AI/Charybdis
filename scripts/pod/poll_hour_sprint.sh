#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
echo TIME=$(date -u +%H:%M:%SZ) pod=ultimate_sapphire_beetle
pgrep -c -f hybrid_validate 2>/dev/null || echo 0
pgrep -af "pod_hour_sprint|pod_highres_bathy|pod_integration_grade|prepare_noaa|real_bathymetry" | head -8 || echo idle
tail -6 /tmp/pod_hour_sprint_stdout.log 2>/dev/null
tail -4 /tmp/pod_highres_bathy.log 2>/dev/null
tail -4 /tmp/pod_integration_grade_stdout.log 2>/dev/null
REMOTE
