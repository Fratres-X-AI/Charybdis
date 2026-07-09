#!/usr/bin/env bash
set -euo pipefail

HOST="root@64.247.206.218"
PORT="14049"
KEY="${HOME}/.ssh/id_ed25519"
LOCAL="$(cd "$(dirname "$0")/../.." && pwd)"

sed -i 's/\r$//' "${LOCAL}/scripts/real_bathymetry_validate.py"

scp -P "$PORT" -i "$KEY" -o StrictHostKeyChecking=no \
  "${LOCAL}/scripts/real_bathymetry_validate.py" \
  "${HOST}:/workspace/Charybdis/scripts/"

ssh -p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=15 "$HOST" 'bash -s' <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
sed -i 's/\r$//' scripts/real_bathymetry_validate.py
grep -n "as_position" scripts/real_bathymetry_validate.py || true
find . -path './scripts/__pycache__' -prune -o -name '*.pyc' -print -delete 2>/dev/null || true
REMOTE
