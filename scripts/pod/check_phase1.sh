#!/usr/bin/env bash
set -euo pipefail

HOST="root@64.247.206.218"
PORT="14049"
KEY="${HOME}/.ssh/id_ed25519"
SSH_OPTS=(-p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no -o BatchMode=yes -T)

ssh "${SSH_OPTS[@]}" "$HOST" 'bash -s' <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
LOG=logs/pod/phase1.log
NOHUP=logs/pod/phase1.nohup

echo "=== check $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "cpus: $(nproc)"
if [[ -f "$NOHUP" ]]; then
  pid=$(cat "$NOHUP")
  if kill -0 "$pid" 2>/dev/null; then
    echo "status: running pid=$pid"
  else
    echo "status: finished pid=$pid exit=$?"
  fi
else
  echo "status: not_started"
fi

if pgrep -af "phase1_pod.sh" >/dev/null 2>&1; then
  pgrep -af "phase1_pod.sh" || true
fi

if [[ -f "$LOG" ]]; then
  echo "--- tail ---"
  tail -n 20 "$LOG" || true
else
  echo "log: missing"
fi
REMOTE
