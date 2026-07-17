#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/pod_env.sh"
HOST="${POD_HOST#root@}"
DEST="$LOCAL_ROOT/artifacts/pod_h200_final_20260717T191348Z"
mkdir -p "$DEST/validation" "$DEST/logs"

echo "=== pull full_pass only -> $DEST ==="
scp -o StrictHostKeyChecking=no -P "$POD_PORT" -i "$POD_KEY" -r \
  "root@$HOST:/workspace/Charybdis/artifacts/validation/20260717T191623Z-e832541" \
  "$DEST/validation/" || true

for f in pod_h200_lane0.log pod_h200_lane1.log pod_h200_followon.log pod_post_train_full_pass.log; do
  scp -o StrictHostKeyChecking=no -P "$POD_PORT" -i "$POD_KEY" \
    "root@$HOST:/tmp/$f" "$DEST/logs/" 2>/dev/null || true
done

echo "FULLPASS_PULL_DONE"
du -sh "$DEST/validation/20260717T191623Z-e832541" 2>/dev/null || true
find "$DEST/validation" -name 'FULL_PASS*' 2>/dev/null
ls -lh "$DEST/models/tcm_so2_h200_lane"*_pass05.pt 2>/dev/null
