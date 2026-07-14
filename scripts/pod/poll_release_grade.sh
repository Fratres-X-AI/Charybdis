#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" 'cd /workspace/Charybdis && echo TIME=$(date -u +%H:%M:%SZ) && pgrep -af pod_release_grade || echo no_release_proc && pgrep -c -f hybrid_validate || echo 0_validate_procs && tail -4 /tmp/pod_release_grade_stdout.log 2>/dev/null; tail -2 /tmp/pod_rel_harbor.log 2>/dev/null; tail -2 /tmp/pod_rel_deep.log 2>/dev/null'
