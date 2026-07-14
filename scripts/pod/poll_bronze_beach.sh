#!/usr/bin/env bash
HOST=root@213.173.107.32
PORT=37613
KEY="${HOME}/.ssh/id_ed25519"
ssh -o StrictHostKeyChecking=no -p "$PORT" -i "$KEY" "$HOST" <<'REMOTE'
ts() { date -u +"%H:%M:%S"; }
echo "=== $(ts) UTC beach ==="
pgrep -af "pod_bronze_beach|pytest" || echo "no active procs"
echo "--- beach log ---"
tail -n 10 /tmp/pod_bronze_beach.log 2>/dev/null || true
echo "--- harbor ---"
tail -n 2 /tmp/pod_beach_harbor.log 2>/dev/null || true
echo "--- deep ---"
tail -n 2 /tmp/pod_beach_deep.log 2>/dev/null || true
echo "python_procs=$(pgrep -c python || echo 0) load=$(cut -d' ' -f1-3 /proc/loadavg)"
REMOTE
