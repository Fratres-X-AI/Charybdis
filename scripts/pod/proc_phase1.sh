#!/usr/bin/env bash
set -euo pipefail

HOST="root@64.247.206.218"
PORT="14049"
KEY="${HOME}/.ssh/id_ed25519"
SSH_OPTS=(-p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no -o BatchMode=yes -T)

ssh "${SSH_OPTS[@]}" "$HOST" 'bash -s' <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
echo "=== proc $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
pid=$(cat logs/pod/phase1.nohup 2>/dev/null || echo none)
ps -o pid,ppid,pcpu,pmem,etime,cmd -p "$pid" 2>/dev/null || true
pgrep -af "pip|pytest|ruff|mypy|python -m build" || true
wc -l logs/pod/phase1.log 2>/dev/null || true
REMOTE
