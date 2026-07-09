#!/usr/bin/env bash
set -e
cd /workspace/Charybdis
source .venv/bin/activate
export PYTHONPATH=.
export PYTHONUNBUFFERED=1
echo "[$(date -u +%H:%M:%S)] GPU train A100 start" >> pod_today.log
python -u <<'PY'
import torch
print("cuda", torch.cuda.is_available(), torch.cuda.get_device_name(0))
from charybdis.experimental.nn_matcher import train
train(epochs=8, n_samples=12000, batch=512, device="cuda")
from charybdis.experimental.nn_matcher import eval_hard
print("hard eval:", eval_hard("models/tcm_so2.pt", n=8192))
PY
echo "[$(date -u +%H:%M:%S)] GPU train done" >> pod_today.log
