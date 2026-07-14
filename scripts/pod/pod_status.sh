#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
echo TIME=$(date -u +%H:%M:%SZ) pod=ultimate_sapphire_beetle
echo cpus=$(nproc) load=$(cat /proc/loadavg)
echo gpus=$(nvidia-smi -L 2>/dev/null | wc -l)
nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader 2>/dev/null || echo no_gpu
echo validate_workers=$(pgrep -c -f hybrid_validate 2>/dev/null || echo 0)
echo real_bathy_workers=$(pgrep -c -f real_bathymetry_validate 2>/dev/null || echo 0)
pgrep -af 'pod_release|pod_cpu_chain|pod_worst|pod_max|pod_integration|pod_highres|hybrid_validate|real_bathymetry' 2>/dev/null | head -12 || echo idle
REMOTE
