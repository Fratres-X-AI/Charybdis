#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" 'cd /workspace/Charybdis && ROOT=$(ls -td artifacts/validation/*/integration_grade 2>/dev/null | head -1) && echo root=$ROOT && python3 - <<"PY"
import json
from pathlib import Path
root = Path(sorted(Path("artifacts/validation").glob("*/integration_grade"), key=lambda p: p.stat().st_mtime)[-1])
for label, sub in (("harbor", "engineering"), ("deep", "deep_engineering")):
    p = root / sub / "matrix_summary.json"
    d = json.loads(p.read_text())
    rows = []
    for name, sc in d.get("scenarios", {}).items():
        r = sc.get("results", {})
        rows.append((r.get("cep95_m", 99), name, sc.get("assessment", {}).get("passed")))
    rows.sort(reverse=True)
    print(f"=== {label} worst cep95 ===")
    for cep, name, ok in rows[:4]:
        print(f"  {name}: cep95={cep:.3f}m passed={ok}")
PY'