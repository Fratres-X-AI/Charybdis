#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
echo "=== status $(date -u +%H:%M:%SZ) ==="
pgrep -af 'pod_elite|hybrid_validate|pod_quad|pod_max_gpu' | head -15 || echo no_procs
echo "--- stdout ---"
tail -25 /tmp/pod_elite_phase34_stdout.log 2>/dev/null || true
echo "--- log ---"
tail -15 /tmp/pod_elite_phase34.log 2>/dev/null || true
echo "--- gpu ---"
nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader 2>/dev/null || true
REMOTE
