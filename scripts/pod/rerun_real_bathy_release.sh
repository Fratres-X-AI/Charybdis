#!/usr/bin/env bash
set -euo pipefail
HOST="root@64.247.206.218"
PORT="14049"
KEY="${HOME}/.ssh/id_ed25519"
LOCAL="$(cd "$(dirname "$0")/../.." && pwd)"

scp -P "$PORT" -i "$KEY" -o StrictHostKeyChecking=no \
  "${LOCAL}/scripts/real_bathymetry_validate.py" \
  "${HOST}:/workspace/Charybdis/scripts/"

ssh -p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no "$HOST" 'bash -s' <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
sed -i 's/\r$//' scripts/real_bathymetry_validate.py
source .venv/bin/activate
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

ROOT=$(ls -dt artifacts/validation/*-fix 2>/dev/null | head -1)
TILE="${ROOT}/real_bathymetry/gebco_monterey.npz"
python scripts/real_bathymetry_validate.py \
  --tile "${TILE}" \
  --tier release \
  --runs 256 \
  --workers 31 \
  --seeds validation/seeds_v1.txt \
  --output "${ROOT}/real_bathymetry/release.json"

(
  cd "${ROOT}"
  sha256sum real_bathymetry/release.json real_bathymetry/release.md >> SHA256SUMS
)
echo "release_real_bathymetry_done ${ROOT}"
REMOTE
