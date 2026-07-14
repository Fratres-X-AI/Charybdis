#!/usr/bin/env bash
HOST=root@213.173.107.32
PORT=37613
KEY="${HOME}/.ssh/id_ed25519"
REMOTE_STAMP="${1:-20260714T153106Z-ad7fa3e}"
ssh -o StrictHostKeyChecking=no -p "$PORT" -i "$KEY" "$HOST" <<REMOTE
ROOT=/workspace/Charybdis/artifacts/validation/${REMOTE_STAMP}
echo "=== matrix summaries ==="
for f in engineering/release/deep_engineering/deep_release; do
  p="\${ROOT}/\${f}/matrix_summary.json"
  if [[ -f "\$p" ]]; then
    echo "--- \$f ---"
    python3 -c "import json; d=json.load(open('\$p')); print('passed=', d.get('passed'), 'scenarios=', len(d.get('scenarios',[])))"
  fi
done
echo "--- real bathymetry ---"
for f in engineering.json release.json; do
  p="\${ROOT}/real_bathymetry/\$f"
  if [[ -f "\$p" ]]; then
    python3 -c "import json; d=json.load(open('\$p')); print('\$f', 'passed=', d.get('passed'), 'cep95=', d.get('cep95_m'))"
  fi
done
echo "--- SHA256 ---"
head -5 "\${ROOT}/SHA256SUMS" 2>/dev/null || true
REMOTE
