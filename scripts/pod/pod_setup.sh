#!/usr/bin/env bash
# Pod setup: serial pytest only (31 workers reserved for MC scripts, not xdist).
set -e
ts(){ date -u +"%H:%M:%S"; }
log(){ echo "[$(ts)] $*"; }

cd /workspace 2>/dev/null || cd ~
log "clone/update Charybdis"
if [ -d Charybdis/.git ]; then
  cd Charybdis && git fetch --all -q && git checkout main -q && git pull -q
else
  git clone -q https://github.com/Fratres-X-AI/Charybdis.git && cd Charybdis
fi

log "venv + deps"
python3 -m venv .venv
. .venv/bin/activate
pip install -q -U pip
pip install -q numpy scipy matplotlib pandas pytest

export PYTHONPATH=. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
log "pytest serial (no xdist)"
python -m pytest -q -n 0
log "SETUP DONE"
echo done > /root/setup.done
