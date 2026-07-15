#!/usr/bin/env bash
# Saturate pod: metric sprint + max_out + mission matrix (all detached).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

echo "=== POD SATURATE: ${POD_NAME} (${POD_HOST}:${POD_PORT}) ==="
bash "$LOCAL_ROOT/scripts/pod/sync_pod.sh"
bash "$LOCAL_ROOT/scripts/pod/kick_metric_sprint.sh"
bash "$LOCAL_ROOT/scripts/pod/kick_pod_max.sh"
bash "$LOCAL_ROOT/scripts/pod/kick_mission_matrix.sh"
bash "$LOCAL_ROOT/scripts/pod/pod_status.sh"
