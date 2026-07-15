#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<REMOTE
cd /workspace/Charybdis
echo TIME=\$(date -u +%H:%M:%SZ) pod=${POD_NAME}
echo load=\$(cat /proc/loadavg)
echo validate=\$(pgrep -c -f hybrid_validate 2>/dev/null || echo 0)
echo bathy=\$(pgrep -c -f real_bathymetry_validate 2>/dev/null || echo 0)
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader 2>/dev/null || true
pgrep -af 'pod_max_out|hybrid_validate|real_bathymetry' 2>/dev/null | head -8 || echo idle
tail -4 /tmp/pod_max_out_stdout.log 2>/dev/null || true
tail -2 /tmp/pod_max_harbor_rel.log 2>/dev/null || true
tail -2 /tmp/pod_max_deep_rel.log 2>/dev/null || true
REMOTE
