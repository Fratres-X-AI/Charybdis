#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
POLL="$SCRIPT_DIR/poll_integration_grade.sh"
LOG="$(cd "$SCRIPT_DIR/../.." && pwd)/artifacts/pod_live_updates_30m.log"
: >"$LOG"
for i in $(seq 1 30); do
  {
    echo "--- UPDATE $i/30 $(date -u +%H:%M:%SZ) ---"
    bash "$POLL" 2>&1 | tail -10
    echo
  } | tee -a "$LOG"
  if [[ $i -lt 30 ]]; then
    sleep 60
  fi
done
echo "MONITOR_DONE $(date -u +%H:%M:%SZ)" | tee -a "$LOG"
