#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/pod_env.sh"
ssh -o StrictHostKeyChecking=no -o ConnectTimeout=12 -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set +e
date -u +%H:%M:%SZ
nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader
echo "r2=$(pgrep -c -f pod_h200_max_gpu_lane || echo 0)"
echo "=== models ==="
ls -lh /workspace/Charybdis/models/tcm_so2_h200*.pt 2>/dev/null || echo "no h200 pts"
ls -lh /workspace/Charybdis/models/tcm_so2.pt /workspace/Charybdis/models/tcm_so2_best*.pt 2>/dev/null | head -8
echo "=== logs ==="
for g in 0 1; do
  echo "--- lane$g ---"
  grep -E 'H200 FINAL|H200 PASS' /tmp/pod_h200_lane${g}.log 2>/dev/null | tail -6
done
echo "=== followon ==="
tail -5 /tmp/pod_h200_followon.log 2>/dev/null || true
REMOTE
