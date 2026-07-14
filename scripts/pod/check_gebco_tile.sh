#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" 'ls -la /workspace/Charybdis/artifacts/validation/*/real_bathymetry/gebco_monterey.npz 2>/dev/null | tail -3 || echo no_gebco_tile'
