#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/pod/pod_env.sh
source "$SCRIPT_DIR/pod_env.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" bash -s <<'REMOTE'
grep -A3 "deep_dvl_dropout" /workspace/Charybdis/charybdis/evaluation/deep_scenarios.py | head -8
python3 - <<'PY'
from charybdis.evaluation.deep_scenarios import deep_validation_gates
g = deep_validation_gates("deep_dvl_dropout")
print("gate", g.max_gps_reacquisition_jump_m)
PY
REMOTE
