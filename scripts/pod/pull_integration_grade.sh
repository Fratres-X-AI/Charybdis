#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
DEST="$LOCAL_ROOT/artifacts/pod_integration_pull_${STAMP}"
mkdir -p "$DEST"
REMOTE_DIR=$(
  ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
    'ls -td /workspace/Charybdis/artifacts/validation/*/integration_grade 2>/dev/null | head -1'
)
if [[ -z "$REMOTE_DIR" ]]; then
  echo "no remote integration_grade artifact found" >&2
  exit 1
fi
scp -P "$POD_PORT" -i "$POD_KEY" -r "$POD_HOST:$REMOTE_DIR/"* "$DEST/"
mkdir -p "$DEST/logs"
scp -P "$POD_PORT" -i "$POD_KEY" "$POD_HOST:/tmp/pod_integration_grade_stdout.log" "$DEST/logs/" 2>/dev/null || true
scp -P "$POD_PORT" -i "$POD_KEY" "$POD_HOST:/tmp/pod_integration_grade.log" "$DEST/logs/" 2>/dev/null || true
echo "PULL_COMPLETE dest=$DEST"
