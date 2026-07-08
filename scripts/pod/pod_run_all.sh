#!/usr/bin/env bash
set -euo pipefail
cd /workspace/Charybdis
source .venv/bin/activate
pip install -U pip -q
pip install -r requirements.txt pytest -q
pip install torch --index-url https://download.pytorch.org/whl/cu126 -q
python - <<'PY'
import torch
print("torch", torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu")
PY
echo "=== BASE TESTS ==="
python -m pytest -q --ignore=tests/test_final4.py
echo "=== TRAIN NN (GPU) ==="
python scripts/train_tcm_nn.py
echo "=== FINAL4 TESTS ==="
python -m pytest tests/test_final4.py -q
echo "=== BENCHMARK ==="
python scripts/benchmark_15of15.py
ls -la models/
