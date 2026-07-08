#!/usr/bin/env bash
set -e
export OMP_NUM_THREADS=31 MKL_NUM_THREADS=31 OPENBLAS_NUM_THREADS=31
LOG=/workspace/Charybdis/run.log
cd /workspace/Charybdis
source .venv/bin/activate
ts(){ date -u +"%H:%M:%S"; }
log(){ echo "[$(ts)] $*"; }
log "START pipeline (target 31 CPU)"
log "minimal pip (no streamlit reinstall)"
pip install -q numpy scipy matplotlib pandas pytest pytest-xdist 2>/dev/null || true
log "torch cu126"
pip install -q torch --index-url https://download.pytorch.org/whl/cu126
python -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"
log "compileall -j 31"
python -m compileall -q -j 31 charybdis . 2>/dev/null || python -m compileall -q charybdis charybdis_*.py run_sim.py scripts 2>/dev/null || true
log "base pytest x31"
python -m pytest -q --ignore=tests/test_final4.py -n 31
log "train NN GPU batch=1024 workers=31"
python -c "from charybdis_nn import train; train(n_samples=24000, epochs=12, batch=1024, seed=0)"
log "final4 pytest x31"
python -m pytest tests/test_final4.py -q -n 31
log "benchmark (swarm workers=31)"
python scripts/benchmark_15of15.py
log "git status"
git add -A && git status --short || true
log "DONE exit=0"
echo 0 > /workspace/Charybdis/run.exit
