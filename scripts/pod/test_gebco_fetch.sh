#!/usr/bin/env bash
set -euo pipefail

HOST="${POD_HOST:-root@64.247.206.218}"
PORT="${POD_PORT:-14049}"
KEY="${POD_KEY:-${HOME}/.ssh/id_ed25519}"

ssh -p "${PORT}" -i "${KEY}" -o BatchMode=yes -T "${HOST}" 'bash -s' <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
source .venv/bin/activate
python scripts/prepare_gebco_tile.py \
  --output artifacts/validation/gebco-smoke/tile.npz \
  --download artifacts/validation/gebco-smoke/source.nc
python scripts/real_bathymetry_validate.py \
  --tile artifacts/validation/gebco-smoke/tile.npz \
  --tier engineering \
  --runs 8 \
  --workers 4 \
  --output artifacts/validation/gebco-smoke/result.json
REMOTE
