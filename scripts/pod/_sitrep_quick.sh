#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/pod_env.sh"
USER="${POD_USER:-root}"
HOST="${POD_HOST#root@}"
HOST="${HOST#*@}"

echo "=== CONNECT $USER@$HOST:$POD_PORT ==="
ssh -o BatchMode=yes -o ConnectTimeout=12 -p "$POD_PORT" -i "$POD_KEY" "$USER@$HOST" bash -s <<'EOF'
set +e
echo "=== GPU ==="
nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total --format=csv,noheader
echo "=== WORK (top) ==="
ps -eo pid,etime,cmd | grep -E 'train_tcm|validate_cep|hotzone|full_pass|python' | grep -v grep | head -20
echo "=== MODELS ==="
ls -lh /workspace/Charybdis/models/tcm_so2.pt \
  /workspace/Charybdis/models/tcm_so2_best.pt \
  /workspace/Charybdis/models/tcm_so2_h200_lane0_pass05.pt \
  /workspace/Charybdis/models/tcm_so2_h200_lane1_pass05.pt 2>&1
echo "=== FULL_PASS MARKERS ==="
ls -1 /workspace/Charybdis/artifacts/validation/*/full_pass/FULL_PASS_* 2>/dev/null
du -sh /workspace/Charybdis/artifacts/validation 2>/dev/null
echo "=== DISK ==="
df -h /workspace | tail -1
EOF
