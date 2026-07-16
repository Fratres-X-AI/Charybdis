#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
echo "=== $(date -u +%H:%M:%SZ) ${POD_NAME:-pod} elite phase34 ==="
echo "cpus=$(nproc) load=$(cat /proc/loadavg)"
echo "validate_workers=$(pgrep -c -f hybrid_validate 2>/dev/null || echo 0)"
echo "real_bathy_workers=$(pgrep -c -f real_bathymetry_validate 2>/dev/null || echo 0)"
echo "gpu_procs=$(pgrep -c -f 'pod_max_gpu_lane|pod_quad_gpu' 2>/dev/null || echo 0)"
nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total --format=csv,noheader 2>/dev/null || true
pgrep -af 'pod_elite_phase34|pod_hybrid_phase2|pod_quad_gpu|pod_max_gpu_lane|hybrid_validate|real_bathymetry|pod_worst|pod_highres|pod_max_out|pod_integration|pod_release' 2>/dev/null | head -22 || echo idle
echo "--- milestones ---"
grep -E 'COMPLETE|START|SKIP' /tmp/pod_elite_phase34.log 2>/dev/null | tail -12 || echo "(no milestones yet)"
echo "--- stdout tail ---"
tail -5 /tmp/pod_elite_phase34_stdout.log 2>/dev/null || true
echo "--- latest artifacts ---"
ls -1dt artifacts/validation/* 2>/dev/null | head -8 || echo none
REMOTE
