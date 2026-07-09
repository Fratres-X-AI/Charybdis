#!/usr/bin/env bash
# Rerun Phase 2 validation after local fixes (engineering matrix + real bathy).
set -euo pipefail

HOST="root@64.247.206.218"
PORT="14049"
KEY="${HOME}/.ssh/id_ed25519"
LOCAL="$(cd "$(dirname "$0")/../.." && pwd)"

bash "$(dirname "$0")/sync_to_pod.sh"

ssh -p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no "$HOST" 'bash -s' <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
mkdir -p logs/pod
LOG=logs/pod/phase2_rerun.log
NOHUP=logs/pod/phase2_rerun.nohup

if pgrep -f "phase2_rerun_inner" >/dev/null 2>&1; then
  echo "already_running"
  exit 0
fi

nohup bash -c '
set -euo pipefail
cd /workspace/Charybdis
source .venv/bin/activate
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export MPLBACKEND=Agg

STAMP="$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD)-fix"
ROOT_OUT="artifacts/validation/${STAMP}"
mkdir -p "${ROOT_OUT}"
python -m pip freeze > "${ROOT_OUT}/requirements-freeze.txt"

echo "=== engineering matrix ==="
python scripts/hybrid_validate_matrix.py \
  --tier engineering \
  --runs 64 \
  --workers 31 \
  --seeds validation/seeds_v1.txt \
  --output-dir "${ROOT_OUT}/engineering" \
  --allow-dirty

echo "=== release matrix ==="
python scripts/hybrid_validate_matrix.py \
  --tier release \
  --runs 256 \
  --workers 31 \
  --seeds validation/seeds_v1.txt \
  --output-dir "${ROOT_OUT}/release" \
  --allow-dirty

TILE="${ROOT_OUT}/real_bathymetry/gebco_monterey.npz"
python scripts/prepare_gebco_tile.py \
  --output "${TILE}" \
  --download "${ROOT_OUT}/real_bathymetry/gebco_subset.nc"

python scripts/real_bathymetry_validate.py \
  --tile "${TILE}" \
  --tier engineering \
  --runs 64 \
  --workers 31 \
  --seeds validation/seeds_v1.txt \
  --output "${ROOT_OUT}/real_bathymetry/engineering.json"

python scripts/real_bathymetry_validate.py \
  --tile "${TILE}" \
  --tier release \
  --runs 256 \
  --workers 31 \
  --seeds validation/seeds_v1.txt \
  --output "${ROOT_OUT}/real_bathymetry/release.json"

python scripts/stress_run.py 64 | tee "${ROOT_OUT}/legacy_stress.log"

(
  cd "${ROOT_OUT}"
  sha256sum \
    requirements-freeze.txt \
    engineering/*.json \
    engineering/REPORT.md \
    release/*.json \
    release/REPORT.md \
    real_bathymetry/*.json \
    real_bathymetry/*.md \
    real_bathymetry/*.npz \
    real_bathymetry/*.nc \
    legacy_stress.log > SHA256SUMS
)

echo "hybrid validation artifacts: ${ROOT_OUT}"
' >>"$LOG" 2>&1 < /dev/null &

echo $! >"$NOHUP"
echo "rerun_started $(cat "$NOHUP")"
REMOTE
