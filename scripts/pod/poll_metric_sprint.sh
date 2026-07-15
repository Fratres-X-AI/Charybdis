#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
echo "TIME=$(date -u +%H:%M:%SZ) pod=sour_aqua_halibut"
echo "sha=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
pgrep -af 'pod_metric_sprint|pod_highres|pod_integration|hybrid_validate|real_bathymetry|pip install|bootstrap' || echo idle
echo "--- metric sprint stdout ---"
tail -8 /tmp/pod_metric_sprint_stdout.log 2>/dev/null || echo no_metric_stdout
echo "--- highres log ---"
tail -5 /tmp/pod_highres_bathy.log 2>/dev/null || echo no_highres_log
echo "--- integration log ---"
tail -5 /tmp/pod_integration_grade.log 2>/dev/null || echo no_integration_log
REMOTE
