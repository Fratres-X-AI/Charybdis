#!/usr/bin/env bash
set -euo pipefail

HOST="root@64.247.206.218"
PORT="14049"
KEY="${HOME}/.ssh/id_ed25519"

ssh -p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=15 "$HOST" 'bash -s' <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
ROOT=artifacts/validation/20260709T200137Z-2e38a82
echo "=== ARTIFACTS ==="
ls -la "$ROOT" 2>/dev/null | head -20 || true
echo "=== ENGINEERING REPORT ==="
head -30 "$ROOT/engineering/REPORT.md" 2>/dev/null || true
echo "=== RELEASE REPORT ==="
head -30 "$ROOT/release/REPORT.md" 2>/dev/null || true
echo "=== ENGINEERING GATES ==="
grep "Gate result" "$ROOT/engineering/REPORT.md" 2>/dev/null || true
echo "=== RELEASE GATES ==="
grep "Gate result" "$ROOT/release/REPORT.md" 2>/dev/null || true
echo "=== REAL BATHY ==="
python3 - <<'PY'
import json, pathlib
root = pathlib.Path("artifacts/validation/20260709T200137Z-2e38a82/real_bathymetry")
for name in ("engineering", "release"):
    p = root / f"{name}.json"
    if p.exists():
        d = json.loads(p.read_text())
        checks = d.get("checks", {})
        print(name, "keys=", sorted(d.keys()))
        print(name, "checks_passed=", all(v.get("passed") for v in checks.values()) if checks else "n/a")
        print(name, "summary=", {k: d.get(k) for k in ("accepted", "runs", "cep95_m", "tier") if k in d})
PY
echo "=== SHA256 ==="
if [[ -f "$ROOT/SHA256SUMS" ]]; then wc -l "$ROOT/SHA256SUMS"; else echo missing; fi
REMOTE
