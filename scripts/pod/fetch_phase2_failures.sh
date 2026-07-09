#!/usr/bin/env bash
set -euo pipefail
HOST="root@64.247.206.218"
PORT="14049"
KEY="${HOME}/.ssh/id_ed25519"
ssh -p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no root@64.247.206.218 'bash -s' <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
ROOT=artifacts/validation/20260709T200137Z-2e38a82
echo "=== ENGINEERING FAILURES ==="
awk '/^### /{s=$0} /Gate result: \*\*FAIL\*\*/{print s}' "$ROOT/engineering/REPORT.md"
echo "=== ENGINEERING DETAILS ==="
grep -B8 "Gate result: \*\*FAIL\*\*" "$ROOT/engineering/REPORT.md" | head -40
echo "=== REPEATED MODE TRANSITIONS CHECKS ==="
python3 - <<'PY'
import json, pathlib
p = pathlib.Path("artifacts/validation/20260709T200137Z-2e38a82/engineering/repeated_mode_transitions.json")
if p.exists():
    d = json.loads(p.read_text())
    for k, v in d["assessment"]["checks"].items():
        print(k, "PASS" if v["passed"] else "FAIL", v)
PY
python3 -c "import json; d=json.load(open('$ROOT/real_bathymetry/engineering.json')); r=d['results']; print('passed',r['passed']); print('status',r['status_counts']); print('checks',r['checks'])"
echo "=== REAL BATHY REL ==="
python3 -c "import json; d=json.load(open('$ROOT/real_bathymetry/release.json')); r=d['results']; print('passed',r['passed']); print('status',r['status_counts']); print('checks',r['checks'])"
REMOTE
