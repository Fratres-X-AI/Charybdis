#!/usr/bin/env bash
HOST=root@213.173.107.32
PORT=37613
KEY="${HOME}/.ssh/id_ed25519"
ssh -o StrictHostKeyChecking=no -p "$PORT" -i "$KEY" "$HOST" <<'REMOTE'
# Kill any prior beach/pytest hogging one core
pkill -f pod_bronze_beach.sh 2>/dev/null || true
pkill -f 'pytest.*not slow' 2>/dev/null || true
sleep 1
pgrep -af 'pod_bronze|pytest|hybrid_validate' || echo "cleared"
REMOTE
