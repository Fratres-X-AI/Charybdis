#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/pod/pod_env.sh
source "$SCRIPT_DIR/pod_env.sh"
DEST="$(cd "$SCRIPT_DIR/../.." && pwd)/artifacts/pod_validation_day_$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$DEST"

echo "=== pull validation_day artifacts ==="
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
  'find /workspace/Charybdis/artifacts/validation -type f \( -name "matrix_summary.json" -o -name "release.json" -o -name "engineering.json" -o -name "REPORT.md" -o -name "*.log" \) -path "*20260716*" 2>/dev/null' \
  | while read -r remote; do
      rel="${remote#/workspace/Charybdis/artifacts/}"
      local_dir="$DEST/validation/$(dirname "$rel")"
      mkdir -p "$local_dir"
      scp -P "$POD_PORT" -i "$POD_KEY" "$POD_HOST:$remote" "$local_dir/" && echo "got $rel"
    done

for f in pod_validation_day.log pod_validation_day_stdout.log; do
  scp -P "$POD_PORT" -i "$POD_KEY" \
    "$POD_HOST:/tmp/$f" "$DEST/logs/" 2>/dev/null && echo "got $f" || true
done

mkdir -p "$DEST/logs"
echo "PULLED $DEST"
