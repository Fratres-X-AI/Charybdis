#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
REMOTE=artifacts/validation/20260714T175959Z-51cc3dd-10481/worst_sweep
LOCAL="$LOCAL_ROOT/artifacts/validation/20260714T175959Z-worst_sweep"
mkdir -p "$LOCAL"
scp -P "$POD_PORT" -i "$POD_KEY" -r "$POD_HOST:/workspace/Charybdis/$REMOTE/"* "$LOCAL/"
echo pulled="$LOCAL"
