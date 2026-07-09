#!/usr/bin/env bash
set -euo pipefail

HOST="root@64.247.206.218"
PORT="14049"
KEY="${HOME}/.ssh/id_ed25519"
LOCAL_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REMOTE_ROOT="/workspace/Charybdis"

ssh -p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no "$HOST" "mkdir -p $REMOTE_ROOT"

tar -C "$LOCAL_ROOT" \
  --no-same-owner \
  --no-same-permissions \
  --exclude=.git \
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
  --exclude='*.pyc' \
  -cf - . | ssh -p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no "$HOST" "tar --no-same-owner -xf - -C $REMOTE_ROOT"

ssh -p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no "$HOST" "for f in $REMOTE_ROOT/scripts/pod/phase1_pod.sh $REMOTE_ROOT/scripts/pod/pod_hybrid_phase2.sh; do sed -i 's/\r$//' \"\$f\"; chmod +x \"\$f\"; done"

echo "sync_ok $REMOTE_ROOT"
