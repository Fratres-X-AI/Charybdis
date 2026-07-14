#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
echo TIME=$(date -u +%H:%M:%SZ)
tail -20 /tmp/pod_max_out_stdout.log 2>/dev/null || true
echo "---"
ls -la artifacts/validation/20260714T194017Z-164ea68-5876/max_out/ 2>/dev/null || true
REMOTE
