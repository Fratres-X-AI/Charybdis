#!/usr/bin/env bash
cd "$(dirname "$0")/../.."
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
DEST="artifacts/pod_quad_final_${STAMP}"
mkdir -p "$DEST/logs" "$DEST/models"
source scripts/pod/pod_env.sh
scp -o StrictHostKeyChecking=no -P "$POD_PORT" -i "$POD_KEY" -r \
  "$POD_HOST:/workspace/Charybdis/artifacts/validation" "$DEST/" 2>/dev/null || true
scp -o StrictHostKeyChecking=no -P "$POD_PORT" -i "$POD_KEY" -r \
  "$POD_HOST:/workspace/Charybdis/models/" "$DEST/" 2>/dev/null || true
for f in pod_quad_cluster.log cluster0.log cluster1.log cluster2.log cluster3.log \
  pod_gpu_lane0.log pod_gpu_lane1.log pod_gpu_lane2.log pod_gpu_lane3.log; do
  scp -o StrictHostKeyChecking=no -P "$POD_PORT" -i "$POD_KEY" \
    "$POD_HOST:/tmp/$f" "$DEST/logs/" 2>/dev/null || true
done
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
  'cd /workspace/Charybdis && git rev-parse HEAD && git log -1 --oneline' > "$DEST/git_state.txt" 2>&1
echo "FINAL_PULL dest=$DEST"
du -sh "$DEST" 2>/dev/null || true
