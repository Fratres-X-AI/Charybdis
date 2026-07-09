#!/usr/bin/env bash
# Resume Phase 2 from real-bathymetry after engineering/release matrices complete.
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
mkdir -p logs/pod
LOG=logs/pod/phase2.log
NOHUP=logs/pod/phase2.nohup

if pgrep -f "scripts/pod/pod_hybrid_phase2.sh" >/dev/null 2>&1; then
  echo "already_running"
  exit 0
fi

ROOT_OUT="$(ls -dt artifacts/validation/* 2>/dev/null | head -1 || true)"
if [[ -z "${ROOT_OUT}" || ! -d "${ROOT_OUT}/engineering" ]]; then
  echo "missing engineering artifacts; run full phase2 instead" >&2
  exit 2
fi

export VALIDATION_WORKERS=31
export ENGINEERING_RUNS=64
export RELEASE_RUNS=256
export LEGACY_STRESS_RUNS=64
export ROOT_OUT
export SEEDS_FILE=validation/seeds_v1.txt

nohup bash -c '
set -euo pipefail
cd /workspace/Charybdis
source .venv/bin/activate
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export MPLBACKEND=Agg

ROOT_OUT="'"${ROOT_OUT}"'"
VALIDATION_WORKERS=31
ENGINEERING_RUNS=64
RELEASE_RUNS=256
LEGACY_STRESS_RUNS=64
SEEDS_FILE=validation/seeds_v1.txt

echo "--- resume phase2 tail $(date -u +%Y-%m-%dT%H:%M:%SZ) ---"

TILE="${ROOT_OUT}/real_bathymetry/gebco_monterey.npz"
if [[ ! -f "${TILE}" ]]; then
  python scripts/prepare_gebco_tile.py \
    --output "${TILE}" \
    --download "${ROOT_OUT}/real_bathymetry/gebco_subset.nc"
fi

if [[ ! -f "${ROOT_OUT}/real_bathymetry/engineering.json" ]]; then
  python scripts/real_bathymetry_validate.py \
    --tile "${TILE}" \
    --tier engineering \
    --runs "${ENGINEERING_RUNS}" \
    --workers "${VALIDATION_WORKERS}" \
    --seeds "${SEEDS_FILE}" \
    --output "${ROOT_OUT}/real_bathymetry/engineering.json"
else
  echo "skip engineering real_bathymetry (artifact exists)"
fi

if [[ ! -f "${ROOT_OUT}/real_bathymetry/release.json" ]]; then
  python scripts/real_bathymetry_validate.py \
    --tile "${TILE}" \
    --tier release \
    --runs "${RELEASE_RUNS}" \
    --workers "${VALIDATION_WORKERS}" \
    --seeds "${SEEDS_FILE}" \
    --output "${ROOT_OUT}/real_bathymetry/release.json"
else
  echo "skip release real_bathymetry (artifact exists)"
fi

if [[ ! -f "${ROOT_OUT}/legacy_stress.log" ]]; then
  python scripts/stress_run.py "${LEGACY_STRESS_RUNS}" \
    | tee "${ROOT_OUT}/legacy_stress.log"
else
  echo "skip legacy stress (artifact exists)"
fi

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
echo "resumed $(cat "$NOHUP") root=${ROOT_OUT}"
REMOTE
