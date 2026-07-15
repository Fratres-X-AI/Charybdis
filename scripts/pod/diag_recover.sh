#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
echo TIME=$(date -u +%H:%M:%SZ)
ps aux | grep -E 'pip|venv|recover|bootstrap|pod_metric|real_bath' | grep -v grep || echo no_procs
echo '--- stdout ---'
tail -25 /tmp/pod_recover_day_stdout.log 2>/dev/null || true
echo '--- log ---'
tail -15 /tmp/pod_recover_day.log 2>/dev/null || true
echo '--- venv ---'
ls -la .venv 2>/dev/null | head -5 || echo no_venv
df -h /workspace /tmp 2>/dev/null || true
REMOTE
