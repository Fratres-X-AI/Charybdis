#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
echo "TIME=$(date -u +%H:%M:%SZ)"
echo "sha=$(git rev-parse --short HEAD)"
echo "validate_workers=$(pgrep -c -f hybrid_validate 2>/dev/null || echo 0)"
echo "--- sprint tail ---"
tail -18 /tmp/pod_metric_sprint_stdout.log 2>/dev/null || true
echo "--- integration tail ---"
tail -12 /tmp/pod_integration_grade.log 2>/dev/null || true
echo "--- artifacts ---"
ls -td artifacts/validation/*/integration_grade 2>/dev/null | head -3 || true
for d in $(ls -td artifacts/validation/*/highres_bathymetry 2>/dev/null | head -1); do
  echo "highres=$d"
  python3 - <<PY
import json
from pathlib import Path
root = Path("$d")
for name in ("engineering", "release"):
    p = root / f"{name}.json"
    if p.exists():
        d = json.loads(p.read_text())
        r = d["results"]
        print(f"  {name}: pass={r['passed']} accepted={r['acceptance_rate']:.3f} cep95={r['cep95_m']:.3f} counts={r['status_counts']}")
PY
done
for d in $(ls -td artifacts/validation/*/integration_grade 2>/dev/null | head -1); do
  if [[ -f "$d/engineering/matrix_summary.json" ]]; then
    echo "integration_harbor=$d/engineering"
    python3 -c "import json; d=json.load(open('$d/engineering/matrix_summary.json')); print('  passed', d.get('passed'))"
  else
    echo "integration_harbor=$d/engineering (pending)"
  fi
  if [[ -f "$d/deep_engineering/matrix_summary.json" ]]; then
    echo "integration_deep=$d/deep_engineering"
    python3 -c "import json; d=json.load(open('$d/deep_engineering/matrix_summary.json')); print('  passed', d.get('passed'))"
  else
    echo "integration_deep=$d/deep_engineering (pending)"
  fi
done
REMOTE
