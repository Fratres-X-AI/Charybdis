#!/usr/bin/env bash
set -euo pipefail
cd /workspace/Charybdis
. .venv/bin/activate
export PYTHONPATH=. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
python -m pytest -q -n 0
python -c "from charybdis.experimental.nn_matcher import train; train(epochs=4,n_samples=4000,device='cuda')" || true
echo done > /root/phases567.done
