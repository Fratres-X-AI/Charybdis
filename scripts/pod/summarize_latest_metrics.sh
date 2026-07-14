#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" 'cd /workspace/Charybdis && python3 - <<"PY"
import json
from pathlib import Path

def load_latest(glob_pat, sub):
    roots = sorted(Path("artifacts/validation").glob(glob_pat), key=lambda p: p.stat().st_mtime)
    if not roots:
        return None
    p = roots[-1] / sub / "matrix_summary.json"
    return json.loads(p.read_text()) if p.exists() else None

def best_worst(d, n=3):
    if not d:
        return []
    rows = [(sc["results"]["cep95_m"], name) for name, sc in d.get("scenarios", {}).items()]
    rows.sort()
    return rows[:n], rows[-n:]

for label, pat, sub in [
    ("integration", "*/integration_grade", "deep_engineering"),
    ("release", "*/release_grade", "deep_release"),
    ("worst", "*/worst_sweep", "deep_worst"),
]:
    d = load_latest(pat, sub)
    if not d:
        print(f"{label}: no data")
        continue
    best, worst = best_worst(d)
    runs = d.get("runs_per_scenario", "?")
    passed = d.get("passed")
    print(f"=== {label} deep ({runs} runs) passed={passed} ===")
    print("  best:", ", ".join(f"{n}={v:.3f}m" for v,n in best))
    print("  worst:", ", ".join(f"{n}={v:.3f}m" for v,n in worst))

h = load_latest("*/integration_grade", "engineering")
if h:
    _, worst = best_worst(h)
    print("=== integration harbor worst ===")
    print("  ", ", ".join(f"{n}={v:.3f}m" for v,n in worst))
PY'