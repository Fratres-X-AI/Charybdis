#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
echo "=== IDLE CHECK $(date -u +%H:%M:%SZ) ==="
echo "validate=$(pgrep -c -f hybrid_validate 2>/dev/null || echo 0)"
echo "bathy=$(pgrep -c -f real_bathymetry_validate 2>/dev/null || echo 0)"
echo "--- mission log ---"
tail -15 /tmp/pod_mission_matrix.log 2>/dev/null || echo "(no mission log)"
echo "--- latest mission artifact ---"
ls -td artifacts/validation/*/mission_engineering 2>/dev/null | head -1 || echo "(none)"
echo "--- max_out summary ---"
python3 - <<'PY'
import json
from pathlib import Path
roots = sorted(Path("artifacts/validation").glob("*/max_out"), key=lambda p: p.stat().st_mtime)
if roots:
    s = json.loads((roots[-1] / "matrix_summary.json").read_text())
    print("max_out:", roots[-1], "passed=", s.get("passed"))
PY
REMOTE
