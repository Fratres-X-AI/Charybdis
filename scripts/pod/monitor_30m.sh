#!/usr/bin/env bash
# 30-minute status monitor: one line per minute to /tmp/pod_monitor_30m.log
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
LOG="$LOCAL_ROOT/artifacts/pod_monitor_30m.log"
: >"$LOG"
for i in $(seq 1 30); do
  TS=$(date -u +%H:%M:%SZ)
  {
    echo "=== UPDATE $i/30 @ $TS ==="
    ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE' 2>/dev/null || echo "ssh_fail"
cd /workspace/Charybdis
echo pod=ultimate_sapphire_beetle
n_val=$(pgrep -c -f hybrid_validate 2>/dev/null || echo 0)
n_pod=$(pgrep -c -f 'pod_' 2>/dev/null || echo 0)
echo workers=$n_val pod_scripts=$n_pod
pgrep -af 'pod_|hybrid_validate|real_bathymetry|prepare_noaa' 2>/dev/null | head -4 || echo idle
tail -3 /tmp/pod_integration_grade_stdout.log 2>/dev/null || true
tail -3 /tmp/pod_hour_sprint_stdout.log 2>/dev/null || true
ls -td artifacts/validation/*/integration_grade 2>/dev/null | head -1 || true
ls -td artifacts/validation/*/highres_bathymetry 2>/dev/null | head -1 || true
REMOTE
  } >>"$LOG"
  sleep 60
done
echo "=== MONITOR_COMPLETE $(date -u +%H:%M:%SZ) ===" >>"$LOG"
