#!/usr/bin/env bash
# Confidence-bounded Phase 2 hybrid validation. Run on the Linux pod only.
set -euo pipefail

REPO="${REPO:-/workspace/Charybdis}"
VALIDATION_WORKERS="${VALIDATION_WORKERS:-31}"
ENGINEERING_RUNS="${ENGINEERING_RUNS:-64}"
RELEASE_RUNS="${RELEASE_RUNS:-256}"
LEGACY_STRESS_RUNS="${LEGACY_STRESS_RUNS:-64}"
SEEDS_FILE="${SEEDS_FILE:-validation/seeds_v1.txt}"

if (( VALIDATION_WORKERS < 1 || VALIDATION_WORKERS > 31 )); then
  echo "VALIDATION_WORKERS must be between 1 and 31" >&2
  exit 2
fi
if (( ENGINEERING_RUNS < 2 || ENGINEERING_RUNS > 512 )); then
  echo "ENGINEERING_RUNS must be between 2 and 512" >&2
  exit 2
fi
if (( RELEASE_RUNS < 2 || RELEASE_RUNS > 512 )); then
  echo "RELEASE_RUNS must be between 2 and 512" >&2
  exit 2
fi
if (( LEGACY_STRESS_RUNS < 1 || LEGACY_STRESS_RUNS > 512 )); then
  echo "LEGACY_STRESS_RUNS must be between 1 and 512" >&2
  exit 2
fi

cd "${REPO}"
source .venv/bin/activate
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export MPLBACKEND=Agg

STAMP="$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD)"
ROOT_OUT="artifacts/validation/${STAMP}"
mkdir -p "${ROOT_OUT}"
python -m pip freeze > "${ROOT_OUT}/requirements-freeze.txt"

python scripts/hybrid_validate_matrix.py \
  --tier engineering \
  --runs "${ENGINEERING_RUNS}" \
  --workers "${VALIDATION_WORKERS}" \
  --seeds "${SEEDS_FILE}" \
  --output-dir "${ROOT_OUT}/engineering" \
  --allow-dirty

python scripts/hybrid_validate_matrix.py \
  --tier release \
  --runs "${RELEASE_RUNS}" \
  --workers "${VALIDATION_WORKERS}" \
  --seeds "${SEEDS_FILE}" \
  --output-dir "${ROOT_OUT}/release" \
  --allow-dirty

python scripts/prepare_gebco_tile.py \
  --output "${ROOT_OUT}/real_bathymetry/gebco_monterey.npz" \
  --download "${ROOT_OUT}/real_bathymetry/gebco_subset.nc"

python scripts/real_bathymetry_validate.py \
  --tile "${ROOT_OUT}/real_bathymetry/gebco_monterey.npz" \
  --tier engineering \
  --runs "${ENGINEERING_RUNS}" \
  --workers "${VALIDATION_WORKERS}" \
  --seeds "${SEEDS_FILE}" \
  --output "${ROOT_OUT}/real_bathymetry/engineering.json"

python scripts/real_bathymetry_validate.py \
  --tile "${ROOT_OUT}/real_bathymetry/gebco_monterey.npz" \
  --tier release \
  --runs "${RELEASE_RUNS}" \
  --workers "${VALIDATION_WORKERS}" \
  --seeds "${SEEDS_FILE}" \
  --output "${ROOT_OUT}/real_bathymetry/release.json"

python scripts/stress_run.py "${LEGACY_STRESS_RUNS}" \
  | tee "${ROOT_OUT}/legacy_stress.log"

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
