#!/usr/bin/env bash
# One clean pull: models + key logs first, then validation. Kill duplicate pulls.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

# Stop duplicate pullers / babysitters thrashing SCP
pkill -f 'pull_h200_shutdown|pull_h200_incremental|away_then_flo' 2>/dev/null || true
sleep 2
# leave one generation — kill stray scp to this host validation pulls
HOST="${POD_HOST#root@}"
HOST="${HOST#*@}"
pkill -f "scp.*${HOST}.*validation" 2>/dev/null || true
sleep 1

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
DEST="$LOCAL_ROOT/artifacts/pod_h200_final_${STAMP}"
mkdir -p "$DEST/models" "$DEST/logs" "$DEST/validation"

echo "=== CRITICAL PULL $STAMP -> $DEST ==="

echo "=== models (first) ==="
scp -o StrictHostKeyChecking=no -P "$POD_PORT" -i "$POD_KEY" -r \
  "$POD_HOST:/workspace/Charybdis/models/" "$DEST/" || true

echo "=== key logs ==="
for f in pod_gpu_lane0.log pod_gpu_lane1.log pod_h200_lane0.log pod_h200_lane1.log \
  pod_h200_followon.log pod_post_train_full_pass.log pod_full_pass.log \
  pod_hotzone_bathy.log pod_cpu_elite.log; do
  scp -o StrictHostKeyChecking=no -P "$POD_PORT" -i "$POD_KEY" \
    "$POD_HOST:/tmp/$f" "$DEST/logs/" 2>/dev/null || true
done

echo "=== git state ==="
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
  'cd /workspace/Charybdis && git rev-parse HEAD; ls -lh models/tcm_so2*.pt | tail -20' \
  > "$DEST/git_state.txt" 2>&1 || true

echo "=== validation (may take a few min) ==="
scp -o StrictHostKeyChecking=no -P "$POD_PORT" -i "$POD_KEY" -r \
  "$POD_HOST:/workspace/Charybdis/artifacts/validation/" "$DEST/" || true

echo "CRITICAL_PULL_COMPLETE dest=$DEST"
du -sh "$DEST" "$DEST/models" "$DEST/validation" 2>/dev/null || true
find "$DEST" -type f | wc -l | xargs -I{} echo "files={}"
ls -lh "$DEST/models/tcm_so2.pt" "$DEST/models/tcm_so2_h200_lane"_pass05.pt 2>/dev/null || ls -lh "$DEST/models"/tcm_so2*.pt 2>/dev/null | tail -12
