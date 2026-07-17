#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
pkill -f 'deadline_pull' 2>/dev/null || true
sleep 1
chmod +x scripts/pod/deadline_pull_90m.sh
nohup bash scripts/pod/deadline_pull_90m.sh > artifacts/deadline_credit_safe.out 2>&1 &
echo "DEADLINE_PID=$!"
sleep 2
ps -ef | grep deadline_pull_90m | grep -v grep || echo "WARN deadline not running"
bash scripts/pod/pull_h200_incremental.sh | tail -12
bash scripts/pod/_r2_eta.sh 2>/dev/null | grep -E 'TIME=|r2_|H200 PASS|H200 FINAL|epoch |^[01],' | head -18
echo "AWAY_OK pull_by=$(date -u -d '+95 minutes' +%H:%M:%SZ 2>/dev/null || date -u -v+95M +%H:%M:%SZ 2>/dev/null || echo '+95m')"
