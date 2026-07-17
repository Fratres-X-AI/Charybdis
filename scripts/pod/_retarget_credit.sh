#!/usr/bin/env bash
# Retarget away_then_flo for new balance: $9.57 / $8.81 ≈ 65 minutes.
# Pull by +50m (15m buffer). FLO only if ≥20m left after pull.
set -euo pipefail
cd "$(dirname "$0")/../.."

pkill -f 'away_then_flo' 2>/dev/null || true
sleep 2

export CHARYBDIS_MAX_MIN=50
export CREDIT_WALL_MIN=60
export MIN_FLO_MINUTES=20

nohup env CHARYBDIS_MAX_MIN=50 CREDIT_WALL_MIN=60 MIN_FLO_MINUTES=20 \
  bash scripts/pod/away_then_flo.sh > artifacts/away_then_flo.out 2>&1 &
echo "RESTARTED_PID=$! CHARYBDIS_MAX=50m CREDIT_WALL=60m"
sleep 2
ps -ef | grep away_then_flo | grep -v grep || echo "WARN not running"
head -8 artifacts/away_then_flo.log 2>/dev/null || true
bash scripts/pod/pull_h200_incremental.sh 2>&1 | tail -8
