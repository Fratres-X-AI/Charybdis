#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis/models 2>/dev/null || exit 1
echo "=== $(date -u +%H:%M:%SZ) ==="
ls -lh tcm_so2*.pt 2>/dev/null | tail -10
NGPU=$(nvidia-smi -L 2>/dev/null | wc -l)
if ! [[ "$NGPU" =~ ^[0-9]+$ ]] || (( NGPU < 1 )); then
  NGPU=4
fi
if (( NGPU > 4 )); then
  NGPU=4
fi
for ((g=0; g<NGPU; g++)); do
  echo -n "gpu${g}: "
  grep -E 'PASS 5/5|FINAL|lane complete|new_best' /tmp/pod_gpu_lane${g}.log 2>/dev/null | tail -2 || echo idle
done
nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader 2>/dev/null
REMOTE
