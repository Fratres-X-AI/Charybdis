#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
echo "--- $(date -u +%H:%M:%SZ) pod recover ---"
echo "cpus=$(nproc) load=$(cat /proc/loadavg)"
echo "validate_workers=$(pgrep -c -f hybrid_validate 2>/dev/null || echo 0)"
echo "real_bathy_workers=$(pgrep -c -f real_bathymetry_validate 2>/dev/null || echo 0)"
pgrep -af 'pod_recover_day|pod_metric|pod_max|pod_release|pod_worst|hybrid_validate|real_bathymetry' 2>/dev/null | head -14 || echo idle
echo "--- recover stdout ---"
tail -8 /tmp/pod_recover_day_stdout.log 2>/dev/null || true
echo "--- recover log ---"
tail -6 /tmp/pod_recover_day.log 2>/dev/null || true
echo "--- latest artifacts ---"
ls -1dt artifacts/validation/* 2>/dev/null | head -5 || echo none
REMOTE
