#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
scp -P "$POD_PORT" -i "$POD_KEY" "$SCRIPT_DIR/pod_worst_sweep.sh" "$POD_HOST:/workspace/Charybdis/scripts/pod/pod_worst_sweep.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" 'sed -i "s/\r$//" /workspace/Charybdis/scripts/pod/pod_worst_sweep.sh && echo worst_sweep_synced'
