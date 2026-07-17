#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=scripts/pod/pod_env.sh
source "$ROOT/scripts/pod/pod_env.sh"

ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set +e
echo "TIME=$(date -u +%H:%M:%SZ)"
nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader
echo "r2_procs=$(pgrep -c -f pod_h200_max_gpu_lane || echo 0)"
for g in 0 1; do
  f=/tmp/pod_h200_lane${g}.log
  echo "=== h200 lane ${g} ==="
  if grep -qE "H200 FINAL gpu=${g}\b" "$f" 2>/dev/null; then
    grep -E "H200 FINAL gpu=${g}\b" "$f" | tail -1
  else
    grep -E 'H200 PASS |epoch |train_wall|new_best|H200 FINAL|vram_mib|h200 lane' "$f" 2>/dev/null | tail -10
  fi
done
REMOTE
