#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
for i in $(seq 1 25); do
  bash "$SCRIPT_DIR/checkin_metric_sprint.sh" | tail -14
  if bash "$SCRIPT_DIR/checkin_metric_sprint.sh" | grep -q 'METRIC_SPRINT_COMPLETE'; then
    echo "DONE"
    exit 0
  fi
  sleep 30
done
echo "TIMEOUT"
exit 1
