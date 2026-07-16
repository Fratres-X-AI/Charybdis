#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/pod/pod_env.sh
source "$SCRIPT_DIR/pod_env.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" bash -s <<'REMOTE'
python3 - <<'PY'
import json
from pathlib import Path

root = sorted(Path("/workspace/Charybdis/artifacts/validation").glob("*/holdout_deep_rerun/deep_release/matrix_summary.json"), key=lambda p: p.stat().st_mtime)[-1]
data = json.loads(root.read_text())
print("FILE", root)
print("OVERALL", data["passed"])
for name, sc in data["scenarios"].items():
    a = sc["assessment"]
    r = sc["results"]
    failed = [k for k, v in a["checks"].items() if not v["passed"]]
    print(
        f"{name}: pass={a['passed']} cep95={r.get('cep95_m',0):.2f} "
        f"gps_jump={r.get('gps_reacquisition_jump_cep95_m',0):.2f} "
        f"route={r.get('route_completion_rate',0):.3f} "
        f"div={r.get('divergence_rate_50m',0):.3f}"
    )
    if failed:
        print("  FAIL_CHECKS", failed)
        for k in failed:
            c = a["checks"][k]
            print(f"    {k}: value={c.get('value')} bound={c.get('bound')}")
PY
REMOTE
