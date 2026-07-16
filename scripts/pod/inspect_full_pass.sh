#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/pod/pod_env.sh
source "$SCRIPT_DIR/pod_env.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" bash -s <<'REMOTE'
python3 - <<'PY'
import json
from pathlib import Path

root = Path("/workspace/Charybdis/artifacts/validation/20260716T115605Z-9f0850b/full_pass")
for label, sub in [
    ("mission", "mission_engineering/matrix_summary.json"),
    ("holdout_harbor", "holdout_harbor/matrix_summary.json"),
    ("holdout_deep", "holdout_deep/matrix_summary.json"),
]:
    p = root / sub
    if not p.exists():
        print(label, "MISSING")
        continue
    d = json.loads(p.read_text())
    print(f"{label}: pass={d['passed']}")
    if not d["passed"]:
        for name, sc in d["scenarios"].items():
            if not sc["assessment"]["passed"]:
                r = sc["results"]
                failed = [k for k,v in sc["assessment"]["checks"].items() if not v["passed"]]
                print(f"  {name}: cep95={r.get('cep95_m',0):.2f} gps_jump={r.get('gps_reacquisition_jump_cep95_m',0):.2f} route={r.get('route_completion_rate',0):.3f} fails={failed}")

hr = sorted(Path("/workspace/Charybdis/artifacts/validation").glob("*/highres_bathymetry/release.json"), key=lambda p: p.stat().st_mtime)[-1]
r = json.loads(hr.read_text())["results"]
print(f"highres: pass={r['passed']} cep95={r['cep95_m']:.3f}")
PY
REMOTE
