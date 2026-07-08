#!/usr/bin/env bash
set -e
cd /workspace/Charybdis
pkill -9 -f 'python.*nn_' 2>/dev/null || true
. .venv/bin/activate
pip install -q torch --index-url https://download.pytorch.org/whl/cu124 2>/dev/null || true
export PYTHONPATH=. OMP_NUM_THREADS=1
python -c "import torch;print(torch.__version__, torch.cuda.is_available())"
python -c "from charybdis.experimental.nn_matcher import train; train()" train 2>/dev/null || python -c "
from charybdis.experimental.nn_matcher import train
train(epochs=6, n_samples=8000, device='cuda')
"
