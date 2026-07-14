#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" 'cd /workspace/Charybdis && echo TIME=$(date -u +%H:%M:%SZ) && echo -n loop_workers= && pgrep -c -f hybrid_validate 2>/dev/null || echo 0 && pgrep -af pod_gebco_job || echo no_gebco && pgrep -af pod_cpu_loop | head -1 && tail -3 /tmp/pod_gebco_stdout.log 2>/dev/null; tail -3 /tmp/pod_cpu_loop_stdout.log 2>/dev/null'
