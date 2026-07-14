#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" 'cd /workspace/Charybdis && echo TIME=$(date -u +%H:%M:%SZ) && pgrep -af pod_integration_grade || echo no_integration_proc && pgrep -af hybrid_validate || echo no_validate_proc && tail -6 /tmp/pod_integration_grade_stdout.log 2>/dev/null || true'
