#!/usr/bin/env bash
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
git log --oneline -1

log "venv + base deps"
python3 -m venv .venv
. .venv/bin/activate
pip install -q -U pip
pip install -q numpy scipy matplotlib pandas pytest pytest-xdist

log "base pytest"
python -m pytest -q -n 16 2>&1 | tail -3

log "SETUP DONE"
echo done > /root/setup.done
