#!/usr/bin/env bash
set -euo pipefail

HOST="${POD_HOST:-root@64.247.206.218}"
PORT="${POD_PORT:-14049}"
KEY="${POD_KEY:-${HOME}/.ssh/id_ed25519}"

ssh -p "${PORT}" -i "${KEY}" -o BatchMode=yes -T "${HOST}" 'bash -s' <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
pid="$(cat logs/pod/phase1.nohup 2>/dev/null || true)"
if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
  pkill -TERM -P "${pid}" 2>/dev/null || true
  kill -TERM "${pid}" 2>/dev/null || true
  echo "stopped ${pid}"
else
  echo "not_running"
fi
REMOTE
