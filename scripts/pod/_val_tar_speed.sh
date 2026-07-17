#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/pod_env.sh"
HOST="${POD_HOST#root@}"
START=$(date +%s)
BYTES=$(ssh -o BatchMode=yes -o ConnectTimeout=15 -p "$POD_PORT" -i "$POD_KEY" "root@$HOST" \
  'tar -C /workspace/Charybdis/artifacts/validation -cf - 20260717T191623Z-e832541' | wc -c)
END=$(date +%s)
ELAPSED=$((END - START))
echo "tar_bytes=$BYTES secs=$ELAPSED"
if [[ "$ELAPSED" -gt 0 ]]; then
  BPS=$((BYTES / ELAPSED))
  echo "Bps=$BPS MBps=$((BPS/1024/1024))"
  LEFT=857287539
  echo "ETA_remaining_at_this_rate_sec=$((LEFT / BPS)) min=$((LEFT / BPS / 60))"
fi
# also size of just the key full_pass run remotely
ssh -o BatchMode=yes -p "$POD_PORT" -i "$POD_KEY" "root@$HOST" \
  'du -sh /workspace/Charybdis/artifacts/validation/20260717T191623Z-e832541'
