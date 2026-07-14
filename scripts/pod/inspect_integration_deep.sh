#!/usr/bin/env bash
source "$(dirname "$0")/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
ROOT=/workspace/Charybdis/artifacts/validation/20260714T173317Z-51cc3dd/integration_grade/deep_engineering
if [[ ! -f "$ROOT/matrix_summary.json" ]]; then
  ROOT=$(ls -td /workspace/Charybdis/artifacts/validation/*/integration_grade/deep_engineering 2>/dev/null | head -1)
fi
echo "deep_root=$ROOT"
python3 -m json.tool "$ROOT/matrix_summary.json" | head -20
for f in "$ROOT"/*.json; do
  base=$(basename "$f")
  [[ "$base" == "matrix_summary.json" ]] && continue
  passed=$(python3 -c "import json; print(json.load(open('$f')).get('passed'))")
  if [[ "$passed" != "True" ]]; then
    echo "FAIL $base passed=$passed"
  fi
done
REMOTE
