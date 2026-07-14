#!/usr/bin/env bash
# Bootstrap venv on pod if missing (first boot only).
set -euo pipefail
REPO=/workspace/Charybdis
cd "$REPO"
if [[ -d .venv ]]; then
  exit 0
fi
echo "[bootstrap] creating venv"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -q -U pip setuptools wheel
python -m pip install -q -c requirements/ci.txt -e ".[dev]"
python -m pip install -q torch --index-url https://download.pytorch.org/whl/cu126
echo "[bootstrap] venv ready"
