#!/usr/bin/env bash
set -e
export PYTHONPATH=/workspace/Charybdis
export OMP_NUM_THREADS=31 MKL_NUM_THREADS=31
cd /workspace/Charybdis
source .venv/bin/activate
ts(){ date -u +"%H:%M:%S"; }
echo "[$(ts)] final4 pytest x31" | tee -a run.log
python -m pytest tests/test_final4.py -q -n 31 | tee -a run.log
echo "[$(ts)] benchmark x31" | tee -a run.log
python scripts/benchmark_15of15.py | tee -a run.log
echo "[$(ts)] ALL DONE" | tee -a run.log
echo 0 > run.exit
