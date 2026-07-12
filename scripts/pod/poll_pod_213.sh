#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
HOST=root@213.192.2.94
PORT=40077
KEY="${HOME}/.ssh/id_ed25519"

for i in $(seq 1 30); do
  echo "CHECK_${i}"
  bash "$ROOT/check_pod_213.sh"
  if ssh -p "$PORT" -i "$KEY" "$HOST" 'grep -q "SPRINT COMPLETE" /tmp/pod_sprint.log 2>/dev/null'; then
    echo DONE
    exit 0
  fi
  if ssh -p "$PORT" -i "$KEY" "$HOST" 'grep -qE "Traceback|Phase 1 pod acceptance passed|hybrid validation artifacts" /tmp/pod_sprint.log 2>/dev/null && ! pgrep -f pod_sprint.sh >/dev/null'; then
    echo STOPPED_EARLY
    ssh -p "$PORT" -i "$KEY" "$HOST" 'tail -n 30 /tmp/pod_sprint.log'
    exit 1
  fi
  sleep 45
done
echo TIMEOUT
exit 2
