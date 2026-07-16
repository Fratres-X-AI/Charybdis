#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
echo "=== $(date -u +%H:%M:%SZ) ==="
nproc
lscpu | egrep 'CPU\(s\)|Thread|Core|Socket|NUMA|Model name' || true
numactl --hardware 2>/dev/null || echo "no numactl"
echo "load=$(cat /proc/loadavg)"
echo "validate=$(pgrep -c -f hybrid_validate 2>/dev/null || echo 0)"
echo "real_bathy=$(pgrep -c -f real_bathymetry 2>/dev/null || echo 0)"
pgrep -af 'hybrid_validate|real_bathymetry|pod_max_gpu' | head -25 || true
echo "--- per-process worker counts ---"
ps -eo args | grep -E 'hybrid_validate|workers' | grep -v grep | head -20 || true
nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader 2>/dev/null || true
REMOTE
