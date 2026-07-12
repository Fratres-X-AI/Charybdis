#!/usr/bin/env bash
set -euo pipefail
HOST=root@213.192.2.94
PORT=40077
KEY="${HOME}/.ssh/id_ed25519"
ssh -p "$PORT" -i "$KEY" "$HOST" <<'REMOTE'
echo "=== $(date -u +%H:%M:%S) UTC ==="
ps aux | grep -E 'pod_sprint|phase1_pod|hybrid_validate|pytest|stress_run|real_bathymetry' | grep -v grep || echo "NO_ACTIVE_WORKERS"
echo "--- key log lines ---"
grep -E 'PHASE|passed|ruff|mypy|harbor_|real_bathymetry|SPRINT|wheel_ok|Phase 1|Phase 2|FAIL|ERROR' /tmp/pod_sprint.log 2>/dev/null | tail -n 20 || true
echo "--- pytest tail ---"
grep -E '^\.|passed in|FAILED|ERROR' /tmp/pod_sprint.log 2>/dev/null | tail -n 3 || true
if test -d /workspace/Charybdis/artifacts/validation; then
  ls -lt /workspace/Charybdis/artifacts/validation 2>/dev/null | head -n 2
fi
REMOTE
