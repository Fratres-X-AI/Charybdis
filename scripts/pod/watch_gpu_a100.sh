#!/usr/bin/env bash
set -euo pipefail
HOST=root@195.26.233.70
PORT=55580
KEY="${HOME}/.ssh/id_ed25519"
LOG=/tmp/pod_gpu_lane0.log

while true; do
  scp -o ConnectTimeout=15 -P "$PORT" -i "$KEY" "${HOST}:/tmp/pod_gpu_lane0.log" "$LOG" 2>/dev/null || true
  if grep -qE 'FINAL gpu=0|lane complete' "$LOG" 2>/dev/null; then
    echo "GPU_DONE"
    grep -E 'FINAL gpu=0|new_best|eval gpu=0' "$LOG" | tail -8
    exit 0
  fi
  echo "$(date -u +%H:%M:%S) $(tail -1 "$LOG" 2>/dev/null || echo waiting)"
  sleep 90
done
