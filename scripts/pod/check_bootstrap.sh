#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/pod/pod_env.sh
source "$SCRIPT_DIR/pod_env.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" bash -s <<'REMOTE'
echo "TIME=$(date -u +%H:%M:%SZ)"
ps aux | grep -E 'pip|venv|bootstrap|pod_validation' | grep -v grep | head -8 || echo "no_bootstrap_procs"
test -d /workspace/Charybdis/.venv && echo "venv=yes" || echo "venv=no"
REMOTE
