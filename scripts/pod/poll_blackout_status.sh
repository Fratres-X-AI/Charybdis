#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" 'cd /workspace/Charybdis && echo "--- $(date -u +%H:%M:%SZ) ---" && pgrep -af hybrid_validate_deep_matrix || echo "no matrix proc" && pgrep -af pod_blackout || echo "no smoke proc" && tail -5 /tmp/pod_blackout_stdout.log 2>/dev/null || true && tail -3 /tmp/pod_blackout_smoke.log 2>/dev/null || true && ls -td artifacts/validation/*/blackout_smoke 2>/dev/null | head -1 | xargs -I{} sh -c "test -f {}/matrix_summary.json && python3 -c \"import json; d=json.load(open(\\\"{}/matrix_summary.json\\\")); print(\\\"RESULT\\\", d.get(\\\"passed\\\"), d.get(\\\"scenarios\\\",{}).get(\\\"deep_long_blackout\\\",{}))\" || echo no_summary_yet"'
