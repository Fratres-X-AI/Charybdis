#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" 'cd /workspace/Charybdis && echo TIME=$(date -u +%H:%M:%SZ) && pgrep -af pod_cpu_followon || echo no_followon && pgrep -af pod_integration_grade || echo no_integration && pgrep -af real_bathymetry || echo no_real_bathy && pgrep -c -f hybrid_validate 2>/dev/null || echo 0 && tail -6 /tmp/pod_cpu_followon_stdout.log 2>/dev/null'
