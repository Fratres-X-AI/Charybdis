#!/usr/bin/env bash
set -euo pipefail

HOST="root@64.247.206.218"
PORT="14049"
KEY="${HOME}/.ssh/id_ed25519"
SSH_OPTS=(-p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no -o BatchMode=yes -T)

ssh "${SSH_OPTS[@]}" "$HOST" 'bash -s' <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
mkdir -p logs/pod
LOG=logs/pod/phase1.log
NOHUP=logs/pod/phase1.nohup

if pgrep -f "scripts/pod/phase1_pod.sh" >/dev/null 2>&1; then
  echo "already_running"
  exit 0
fi

nohup bash scripts/pod/phase1_pod.sh >"$LOG" 2>&1 < /dev/null &
echo $! >"$NOHUP"
echo "started $(cat "$NOHUP")"
REMOTE
