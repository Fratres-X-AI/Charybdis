#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
DEST="$(cd "$SCRIPT_DIR/../.." && pwd)/artifacts/pod_final_pull_20260715T164025Z/logs"
mkdir -p "$DEST"
echo "=== extra logs ==="
for f in pod_recover_day.log pod_recover_day_stdout.log pod_mission_matrix.log; do
  scp -P "$POD_PORT" -i "$POD_KEY" \
    "$POD_HOST:/tmp/$f" "$DEST/" 2>/dev/null && echo "got $f" || echo "skip $f"
done
echo "=== remote dirs ==="
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
  'ls -1d /workspace/Charybdis/artifacts/validation/* 2>/dev/null | wc -l; du -sh /workspace/Charybdis/artifacts/validation 2>/dev/null'
