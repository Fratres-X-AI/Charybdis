#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/pod/pod_env.local.sh"

ssh -o BatchMode=yes -o ConnectTimeout=12 -p "$POD_PORT" -i "$POD_KEY" "$POD_USER@$POD_HOST" bash -s <<'EOF'
echo "=== GPU ==="
nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total --format=csv,noheader
echo "=== WORK ==="
ps -eo pid,etime,cmd | grep -E 'train_tcm|validate_cep|hotzone|full_pass|python' | grep -v grep | head -25 || true
echo "=== MODELS ==="
ls -lh /workspace/Charybdis/models/tcm_so2*.pt 2>/dev/null || true
echo "=== FULL_PASS ==="
ls -1d /workspace/Charybdis/artifacts/validation/*/full_pass 2>/dev/null | tail -3
for d in /workspace/Charybdis/artifacts/validation/*/full_pass; do
  [ -d "$d" ] || continue
  echo "-- $d"
  ls -1 "$d" 2>/dev/null | head -20
done
echo "=== GREEN ==="
if [ -x /workspace/Charybdis/scripts/pod/pod_pipeline_green.sh ]; then
  bash /workspace/Charybdis/scripts/pod/pod_pipeline_green.sh 2>/dev/null | tail -40 || true
fi
EOF
