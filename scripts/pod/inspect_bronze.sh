#!/usr/bin/env bash
HOST=root@213.173.107.32
PORT=37613
KEY="${HOME}/.ssh/id_ed25519"
ssh -o StrictHostKeyChecking=no -p "$PORT" -i "$KEY" "$HOST" <<'REMOTE'
ts() { date -u +"%H:%M:%S"; }
echo "=== $(ts) UTC inspect ==="
ps auxf | head -50
echo "--- venv size ---"
du -sh /workspace/Charybdis/.venv 2>/dev/null || echo no_venv
echo "--- military log ---"
tail -15 /tmp/pod_bronze_military.log 2>/dev/null || true
echo "--- pip children ---"
pgrep -af pip || echo no_pip
REMOTE
