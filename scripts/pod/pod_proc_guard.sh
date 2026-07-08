#!/usr/bin/env bash
# Abort if python process count exceeds limit (prevents 119-proc explosions).
MAX=${CHARYBDIS_MAX_PROCS:-35}
n=$(pgrep -c python 2>/dev/null || echo 0)
if [ "$n" -gt "$MAX" ]; then
  echo "ABORT: $n python processes (max $MAX). Killing all."
  pkill -9 python 2>/dev/null || true
  exit 1
fi
echo "OK: $n python processes"
