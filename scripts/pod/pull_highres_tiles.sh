#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
DEST="$(cd "$SCRIPT_DIR/../.." && pwd)/artifacts/pod_final_pull_20260715T164025Z/validation"
mkdir -p "$DEST"

echo "=== pull NOAA tiles (npz/nc) ==="
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
  'find /workspace/Charybdis/artifacts/validation -type f \( -name "*.npz" -o -name "*.nc" \) 2>/dev/null' \
  | while read -r remote; do
      rel="${remote#/workspace/Charybdis/artifacts/validation/}"
      local_dir="$DEST/$(dirname "$rel")"
      mkdir -p "$local_dir"
      scp -P "$POD_PORT" -i "$POD_KEY" "$POD_HOST:$remote" "$local_dir/" && echo "got $rel"
    done

echo "=== pull size ==="
du -sh "$(cd "$SCRIPT_DIR/../.." && pwd)/artifacts/pod_final_pull_20260715T164025Z"
