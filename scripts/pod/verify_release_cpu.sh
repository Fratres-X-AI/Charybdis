#!/usr/bin/env bash
# Verify release-tier CPU validation from a local artifact pull (no remote GPU).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PULL="${1:-$LOCAL_ROOT/artifacts/pod_h200_final_20260717T143729Z}"
PULL="$(cd "$PULL" 2>/dev/null && pwd || echo "$PULL")"

if [[ ! -d "$PULL/validation" ]]; then
  echo "ERROR: missing validation tree: $PULL/validation"
  exit 1
fi

export PULL_ROOT="$PULL"
python - <<'PY'
import json
import os
import sys
from pathlib import Path

root = Path(os.environ["PULL_ROOT"])
val = root / "validation"
if not val.is_dir():
    print(f"RED missing {val}")
    sys.exit(1)
cpu_dirs = sorted(val.glob("*/cpu_elite"))
if not cpu_dirs:
    print("RED no cpu_elite dir")
    sys.exit(1)
cpu = cpu_dirs[-1]
checks = {}
notes = {}
for job in (
    "mission_engineering",
    "holdout_harbor",
    "holdout_deep",
    "harbor_release",
    "deep_release",
):
    key = f"cpu_{job}"
    summary = cpu / job / "matrix_summary.json"
    if not summary.is_file():
        checks[key] = False
        notes[key] = "missing"
        continue
    checks[key] = bool(json.loads(summary.read_text())["passed"])

highres = sorted((root / "validation").glob("*/highres_bathymetry"))
if highres:
    rel = highres[-1] / "release.json"
    if rel.is_file():
        checks["highres_release"] = bool(json.loads(rel.read_text())["results"]["passed"])
    else:
        checks["highres_release"] = False
else:
    checks["highres_release"] = False

print("=== RELEASE CPU VERIFICATION (local pull) ===")
for name in sorted(checks):
    mark = "GREEN" if checks[name] else "RED"
    print(f"{mark} {name}")
passed = sum(checks.values())
total = len(checks)
overall = passed == total and total > 0
print(f"SCORE {passed}/{total} overall={'GREEN' if overall else 'RED'}")
print(f"artifact_root={root}")
sys.exit(0 if overall else 1)
PY
