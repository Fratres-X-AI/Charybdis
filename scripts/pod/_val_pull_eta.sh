#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/pod_env.sh"
HOST="${POD_HOST#root@}"
LOCAL="$ROOT/artifacts/pod_h200_final_20260717T191348Z/validation"

echo "=== REMOTE validation size ==="
ssh -o BatchMode=yes -o ConnectTimeout=15 -p "$POD_PORT" -i "$POD_KEY" "root@$HOST" \
  'du -sb /workspace/Charybdis/artifacts/validation; du -sh /workspace/Charybdis/artifacts/validation; find /workspace/Charybdis/artifacts/validation -type f | wc -l'

echo "=== LOCAL validation so far ==="
if [[ -d "$LOCAL" ]]; then
  du -sb "$LOCAL" 2>/dev/null || true
  du -sh "$LOCAL" 2>/dev/null || true
  find "$LOCAL" -type f 2>/dev/null | wc -l
else
  echo "0 (missing)"
fi

echo "=== active scp? ==="
ps -ef 2>/dev/null | grep -E "scp.*validation|scp.*${HOST}" | grep -v grep || echo none

echo "=== 15s speed sample (full_pass tree only) ==="
TMP="$ROOT/artifacts/_speedtest_val"
rm -rf "$TMP"
mkdir -p "$TMP"
START=$(date +%s)
# pull just the completed full_pass dir as a speed probe (~smaller than whole tree)
scp -o StrictHostKeyChecking=no -o ConnectTimeout=20 -P "$POD_PORT" -i "$POD_KEY" -r \
  "root@$HOST:/workspace/Charybdis/artifacts/validation/20260717T191623Z-e832541/full_pass" \
  "$TMP/" >/dev/null 2>&1 || true
END=$(date +%s)
ELAPSED=$((END - START))
BYTES=$(du -sb "$TMP" 2>/dev/null | awk '{print $1}')
echo "probe_bytes=$BYTES probe_secs=$ELAPSED"
if [[ "$ELAPSED" -gt 0 && "$BYTES" -gt 0 ]]; then
  BPS=$((BYTES / ELAPSED))
  echo "approx_Bps=$BPS (~$((BPS/1024/1024)) MB/s)"
  REMOTE_B=$(ssh -o BatchMode=yes -o ConnectTimeout=15 -p "$POD_PORT" -i "$POD_KEY" "root@$HOST" \
    'du -sb /workspace/Charybdis/artifacts/validation' | awk '{print $1}')
  LOCAL_B=$(du -sb "$LOCAL" 2>/dev/null | awk '{print $1}')
  LOCAL_B=${LOCAL_B:-0}
  LEFT=$((REMOTE_B - LOCAL_B))
  if [[ "$LEFT" -lt 0 ]]; then LEFT=$REMOTE_B; fi
  if [[ "$BPS" -gt 0 ]]; then
    SECS=$((LEFT / BPS))
    echo "remote_B=$REMOTE_B local_B=$LOCAL_B left_B=$LEFT"
    echo "ETA_secs=$SECS ETA_min=$((SECS/60))"
  fi
fi
rm -rf "$TMP"
