#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
scp -o StrictHostKeyChecking=no -P "$POD_PORT" -i "$POD_KEY" \
  "$SCRIPT_DIR/pod_pipeline_green.sh" \
  "$POD_HOST:/workspace/Charybdis/scripts/pod/pod_pipeline_green.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
  "sed -i 's/\r$//' /workspace/Charybdis/scripts/pod/pod_pipeline_green.sh"
bash "$SCRIPT_DIR/pod_pipeline_green.sh" --report 2>/dev/null | grep -E 'GREEN |RED |SCORE'
