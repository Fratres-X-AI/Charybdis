#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" 'grep -E "LOOP_CYCLE|PASS harbor|PASS deep|WORST_SWEEP|RELEASE_GRADE|INTEGRATION_GRADE|sparse_outlier|deep_long_blackout" /tmp/pod_cpu_loop.log | tail -25'
