#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
pkill -f 'deadline_pull|away_then_flo' 2>/dev/null || true
sleep 1
chmod +x scripts/pod/away_then_flo.sh scripts/pod/deadline_pull_90m.sh
nohup bash scripts/pod/away_then_flo.sh > artifacts/away_then_flo.out 2>&1 &
echo "AWAY_THEN_FLO_PID=$!"
sleep 2
ps -ef | grep away_then_flo | grep -v grep || echo "WARN not running"
head -6 artifacts/away_then_flo.log 2>/dev/null || head -6 artifacts/away_then_flo.out
bash scripts/pod/_r2_eta.sh 2>/dev/null | grep -E 'TIME=|r2_|H200 PASS|H200 FINAL|^[01],' | head -12 || true
echo "READY — Charybdis first; FLO only if credit time left after pull"
