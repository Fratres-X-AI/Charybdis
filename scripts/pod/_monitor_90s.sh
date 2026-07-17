#!/usr/bin/env bash
# Local 90s check-in loop for active H200 run.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
LOG="$ROOT/artifacts/monitor_90s.log"
: >"$LOG"
for i in $(seq 1 80); do
  {
    echo "==== MONITOR $i $(date -u +%H:%M:%SZ) ===="
    bash scripts/pod/_sitrep.sh || true
    bash scripts/pod/_ensure_babysit.sh || true
  } >>"$LOG" 2>&1
  sleep 90
done
