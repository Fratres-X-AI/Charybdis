#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" 'cd /workspace/Charybdis && echo TIME=$(date -u +%H:%M:%SZ) && pgrep -af pod_cpu_chain || echo no_chain && pgrep -af pod_worst_sweep || echo no_worst && pgrep -c -f hybrid_validate 2>/dev/null || echo 0 && tail -5 /tmp/pod_release_grade_stdout.log 2>/dev/null; tail -3 /tmp/pod_cpu_chain_stdout.log 2>/dev/null; tail -2 /tmp/pod_worst_harbor.log 2>/dev/null; tail -2 /tmp/pod_worst_deep.log 2>/dev/null'
