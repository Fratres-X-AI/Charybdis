#!/usr/bin/env bash
set -euo pipefail

HOST=root@157.157.221.29
PORT=30511
KEY="${HOME}/.ssh/id_ed25519"
LOCAL_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REMOTE_ROOT="/workspace/Charybdis"

ssh -p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no "$HOST" "mkdir -p $REMOTE_ROOT"

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
  --exclude=models \
  --exclude=outputs \
  --exclude=.cursor \
  --exclude='*.pyc' \
  -cf - . | ssh -p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no "$HOST" "tar --no-same-owner -xf - -C $REMOTE_ROOT"

ssh -p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no "$HOST" <<'REMOTE'
cd /workspace/Charybdis
for f in scripts/pod/*.sh; do
  sed -i 's/\r$//' "$f"
  chmod +x "$f"
done
echo "sync_ok $(pwd) gpus=$(nvidia-smi -L 2>/dev/null | wc -l)"
REMOTE
