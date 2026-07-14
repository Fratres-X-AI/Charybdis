#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" 'cd /workspace/Charybdis && echo TIME=$(date -u +%H:%M:%SZ) && pgrep -af pod_cpu_loop && pgrep -c -f hybrid_validate && tail -4 /tmp/pod_cpu_loop_stdout.log'
