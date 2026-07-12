#!/usr/bin/env bash
set -euo pipefail
cd /workspace/Charybdis
source .venv/bin/activate
pip install -q torch --index-url https://download.pytorch.org/whl/cu126
python - <<'PY'
from charybdis.experimental.nn_matcher import eval_hard
print(eval_hard("models/tcm_so2.pt", n=4096))
PY
