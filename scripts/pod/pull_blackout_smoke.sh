#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
REMOTE_DIR=artifacts/validation/20260714T174750Z-51cc3dd-6216/blackout_smoke
LOCAL_DIR="$LOCAL_ROOT/artifacts/validation/20260714T174750Z-blackout_smoke"
mkdir -p "$LOCAL_DIR"
scp -P "$POD_PORT" -i "$POD_KEY" -r "$POD_HOST:/workspace/Charybdis/$REMOTE_DIR/"* "$LOCAL_DIR/"
echo pulled_to="$LOCAL_DIR"
