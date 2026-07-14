#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/pod/pod_env.sh
source "$SCRIPT_DIR/pod_env.sh"
KEY="${POD_KEY}"
HOST="${POD_HOST}"
PORT="${POD_PORT}"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REMOTE_ROOT="/workspace/Charybdis"
MODEL_SRC="${LOCAL_ROOT}/models/tcm_so2.pt"
if [[ ! -f "$MODEL_SRC" ]]; then
  MODEL_SRC="${LOCAL_ROOT}/artifacts/pod_a100_pull_20260714/models/tcm_so2.pt"
fi

ssh -o StrictHostKeyChecking=no -p "$PORT" -i "$KEY" "$HOST" "mkdir -p $REMOTE_ROOT/models"

tar -C "$LOCAL_ROOT" \
  --no-same-owner \
  --no-same-permissions \
  --exclude=.venv \
  --exclude=__pycache__ \
  --exclude=.pytest_cache \
  --exclude=.ruff_cache \
  --exclude=artifacts \
  --exclude=dist \
  --exclude=build \
  --exclude=logs \
  --exclude=outputs \
  --exclude=.cursor \
  --exclude='*.pyc' \
  -cf - . | ssh -o StrictHostKeyChecking=no -p "$PORT" -i "$KEY" "$HOST" "tar --no-same-owner -xf - -C $REMOTE_ROOT"

if [[ -f "$MODEL_SRC" ]]; then
  scp -o StrictHostKeyChecking=no -P "$PORT" -i "$KEY" \
    "$MODEL_SRC" "$HOST:$REMOTE_ROOT/models/tcm_so2.pt"
fi

ssh -o StrictHostKeyChecking=no -p "$PORT" -i "$KEY" "$HOST" <<REMOTE
cd /workspace/Charybdis
for f in scripts/pod/*.sh; do
  sed -i 's/\r\$//' "\$f"
  chmod +x "\$f"
done
echo "sync_ok \$(pwd) pod=${POD_NAME} gpus=\$(nvidia-smi -L 2>/dev/null | wc -l) cpus=\$(nproc)"
REMOTE
