#!/usr/bin/env bash
set -euo pipefail

ROOT="/workspace/Charybdis"
cd "$ROOT"

echo "=== Phase 1 pod acceptance ==="
python3 --version
nproc

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip

python -m pip install -c requirements/ci.txt -e ".[dev]"

echo "--- ruff ---"
ruff check charybdis tests scripts examples run_sim.py
ruff format --check charybdis tests scripts examples run_sim.py

echo "--- mypy ---"
mypy charybdis/hybrid \
  charybdis/bathy.py \
  charybdis/simulation/hybrid.py \
  charybdis/evaluation/confidence.py \
  charybdis/evaluation/hybrid.py \
  charybdis/evaluation/scenarios.py \
  charybdis/evaluation/validation.py

echo "--- architecture ---"
python -m pytest tests/test_architecture.py

echo "--- full suite + coverage ---"
export MPLBACKEND=Agg
python -m pytest --timeout=120 --timeout-method=thread \
  -m "not console and not slow" --cov=charybdis --cov-report=term-missing \
  --cov-report=xml --cov-fail-under=80
coverage report --include="charybdis/hybrid/*" --fail-under=90

echo "--- examples ---"
for example in examples/*.py; do
  python "$example" >/dev/null
done

echo "--- wheel build ---"
python -m build
python - <<'PY'
from glob import glob
from zipfile import ZipFile

wheel = glob("dist/*.whl")
assert len(wheel) == 1, wheel
with ZipFile(wheel[0]) as archive:
    names = set(archive.namelist())
assert "charybdis/py.typed" in names
assert not any(name.startswith("console/") for name in names)
print("wheel_ok", wheel[0])
PY

WHEEL="$(python -c 'from glob import glob; print(glob("dist/*.whl")[0])')"
rm -rf /tmp/charybdis-wheel-smoke
python -m venv /tmp/charybdis-wheel-smoke
/tmp/charybdis-wheel-smoke/bin/python -m pip install --quiet "${WHEEL}"
(
  cd /tmp
  /tmp/charybdis-wheel-smoke/bin/python - <<'PY'
import sys

import charybdis

assert charybdis.__version__ == "0.3.0"
assert charybdis.HybridNavigator
assert "torch" not in sys.modules
assert not any(name == "console" or name.startswith("console.") for name in sys.modules)
print("isolated_wheel_import_ok")
PY
)

echo "=== Phase 1 pod acceptance passed ==="
