#!/usr/bin/env bash
set -e
export OMP_NUM_THREADS=31 MKL_NUM_THREADS=31 OPENBLAS_NUM_THREADS=31
cd /workspace/Charybdis
source .venv/bin/activate
ts(){ date -u +"%H:%M:%S"; }
log(){ echo "[$(ts)] $*" | tee -a /workspace/Charybdis/run.log; }
log "RESUME train CPU x31 (5090 needs nightly torch; CPU+31 threads)"
python -c "from charybdis_nn import train; train(n_samples=24000, epochs=12, batch=512, seed=0, device='cpu', num_workers=31)"
log "final4 pytest x31"
python -m pytest tests/test_final4.py -q -n 31
log "benchmark workers=31"
python scripts/benchmark_15of15.py
log "DONE exit=0"
echo 0 > /workspace/Charybdis/run.exit
