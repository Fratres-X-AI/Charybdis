#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
echo "=== GPU lanes $(date -u +%H:%M:%SZ) ==="
for g in 0 1 2 3; do
  echo "--- gpu${g} ---"
  grep -E 'PASS |eval gpu|new_best|FINAL|lane complete' /tmp/pod_gpu_lane${g}.log 2>/dev/null | tail -3 || echo "(no log yet)"
done
echo "=== quad summaries ==="
for f in $(find artifacts/validation -path '*/quad_cluster/matrix_summary.json' 2>/dev/null | tail -4); do
  python3 -c "import json,sys; d=json.load(open('$f')); print('$f', 'passed='+str(d.get('passed')))" 2>/dev/null || true
done
for f in $(find artifacts/validation -path '*/quad_cluster/mission_engineering/matrix_summary.json' 2>/dev/null | tail -2); do
  python3 - <<PY
import json
d=json.load(open("$f"))
print("mission passed=", d.get("passed"))
for n,s in sorted(d.get("scenarios",{}).items()):
    print(f"  {n}: {'PASS' if s['assessment']['passed'] else 'FAIL'}")
PY
done 2>/dev/null || true
REMOTE
