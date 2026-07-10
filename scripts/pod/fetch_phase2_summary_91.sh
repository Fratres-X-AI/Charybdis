#!/usr/bin/env bash
set -euo pipefail
HOST=root@91.199.227.82
PORT=31640
KEY="${HOME}/.ssh/id_ed25519"
ssh -p "$PORT" -i "$KEY" "$HOST" <<'REMOTE'
ROOT=/workspace/Charybdis/artifacts/validation/20260710T084153Z-3226290
cd "$ROOT"
echo "SHA256SUMS:"
test -f SHA256SUMS && wc -l SHA256SUMS || echo MISSING
python3 - <<'PY'
import json
from pathlib import Path
root = Path('.')
for tier in ('engineering', 'release'):
    print(f'=== {tier} ===')
    for path in sorted((root / tier).glob('*.json')):
        data = json.loads(path.read_text())
        passed = data.get('assessment', {}).get('passed', data.get('passed'))
        scenario = path.stem
        print(f'{scenario}: {passed}')
for tier in ('engineering', 'release'):
    p = root / 'real_bathymetry' / f'{tier}.json'
    if p.exists():
        data = json.loads(p.read_text())
        r = data['results']
        print(f'real_bathymetry {tier}: passed={r["passed"]} checks={r["checks"]}')
PY
REMOTE
