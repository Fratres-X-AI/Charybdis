#!/usr/bin/env bash
set -euo pipefail
HOST=root@91.199.227.82
PORT=31640
KEY="${HOME}/.ssh/id_ed25519"
ssh -p "$PORT" -i "$KEY" "$HOST" <<'REMOTE'
ps aux | grep -E 'pip|hybrid_validate|prepare_gebco|pod_bootstrap' | grep -v grep || true
echo '--- /tmp/pod_phase2.log ---'
tail -n 25 /tmp/pod_phase2.log 2>/dev/null || true
echo '--- /tmp/pod_bootstrap.out ---'
tail -n 25 /tmp/pod_bootstrap.out 2>/dev/null || true
if test -d /workspace/Charybdis/artifacts/validation; then
  ls -lt /workspace/Charybdis/artifacts/validation | head -n 3
fi
REMOTE
