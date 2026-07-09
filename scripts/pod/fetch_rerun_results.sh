#!/usr/bin/env bash
set -euo pipefail
HOST="root@64.247.206.218"
PORT="14049"
KEY="${HOME}/.ssh/id_ed25519"
ssh -p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no root@64.247.206.218 'bash -s' <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
ROOT=$(ls -dt artifacts/validation/*-fix 2>/dev/null | head -1)
echo "ROOT=$ROOT"
echo "=== RERUN LOG ==="
tail -40 logs/pod/phase2_rerun.log
echo "=== ENGINEERING GATES ==="
if [[ -f "$ROOT/engineering/REPORT.md" ]]; then
  grep -E "^### |Gate result" "$ROOT/engineering/REPORT.md"
fi
echo "=== REPEATED CHECKS ==="
python3 - <<PY
import json, pathlib, glob
root = sorted(pathlib.Path("artifacts/validation").glob("*-fix"), reverse=True)
if not root:
    raise SystemExit("no fix artifacts")
eng = root[0] / "engineering"
p = eng / "repeated_mode_transitions.json"
if p.exists():
    d = json.loads(p.read_text())
    checks = d["results"]["assessment"]["checks"]
    for k,v in checks.items():
        print(k, "PASS" if v["passed"] else "FAIL", "obs", v["observed"], "thr", v["threshold"])
PY
echo "=== REAL BATHY (latest json) ==="
python3 - <<PY
import json, pathlib
root = sorted(pathlib.Path("artifacts/validation").glob("*-fix"), reverse=True)[0]
for tier in ("engineering", "release"):
    p = root / "real_bathymetry" / f"{tier}.json"
    if p.exists():
        r = json.loads(p.read_text())["results"]
        print(tier, "passed", r["passed"], "accepted", r["status_counts"].get("accepted"))
PY
REMOTE
