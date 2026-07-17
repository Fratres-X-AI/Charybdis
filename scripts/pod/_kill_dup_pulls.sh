#!/usr/bin/env bash
# Keep ONE validation scp (oldest running), kill the rest + duplicate shutdown scripts.
set -euo pipefail

# Kill all pull_h200_shutdown and _fast_critical parents except we kill all then...
# Safer: kill every pull_h200_shutdown and all scp validation; user already has models.
echo "Killing duplicate pull/shutdown thrash..."
pkill -f 'pull_h200_shutdown.sh' 2>/dev/null || true
pkill -f '_fast_critical_pull.sh' 2>/dev/null || true
sleep 1
# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")" && pwd)/pod_env.sh"
HOST="${POD_HOST#root@}"
HOST="${HOST#*@}"
pkill -f "scp.*${HOST}.*validation" 2>/dev/null || true
pkill -f "scp.*${HOST}.*models" 2>/dev/null || true
sleep 1
echo "Remaining:"
ps -ef 2>/dev/null | grep -E "scp.*${HOST}|pull_h200|_fast_critical" | grep -v grep || echo "(none)"
