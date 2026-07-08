#!/usr/bin/env bash
# Generic pod runner: kills stale sweep procs, activates venv, runs a script.
# Usage: bash scripts/pod_exec.sh scripts/pmf_tune.py 48
set -e
cd /workspace/Charybdis
# Kill stale python workers only (pattern excludes this bash launcher).
pkill -9 -f 'python.*pmf_' 2>/dev/null || true
sleep 1
. .venv/bin/activate
export PYTHONPATH=. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
exec python "$@"
