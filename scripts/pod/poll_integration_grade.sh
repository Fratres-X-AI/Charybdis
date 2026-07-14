#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/pod/pod_env.sh
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" "POD_NAME='$POD_NAME' bash -s" <<'REMOTE'
ts() { date -u +"%H:%M:%S"; }
echo "=== $(ts) UTC ${POD_NAME} integration ==="
pgrep -af "pod_integration_grade|hybrid_validate|pytest" || echo "no active procs"
echo "--- log ---"
tail -n 8 /tmp/pod_integration_grade.log 2>/dev/null || true
echo "python=$(pgrep -c python || echo 0) load=$(cut -d' ' -f1-3 /proc/loadavg)"
nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader 2>/dev/null || true
REMOTE
