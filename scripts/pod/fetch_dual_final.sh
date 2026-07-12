#!/usr/bin/env bash
set -euo pipefail
HOST=root@157.157.221.29
PORT=30511
KEY="${HOME}/.ssh/id_ed25519"
LOCAL_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEST="${LOCAL_ROOT}/artifacts/pod_final_pull_20260712"
REMOTE=/workspace/Charybdis

mkdir -p "$DEST"/{models,logs,validation}

scp -P "$PORT" -i "$KEY" -o StrictHostKeyChecking=no \
  "$HOST:$REMOTE/models/tcm_so2.pt" \
  "$HOST:$REMOTE/models/tcm_so2_best.pt" \
  "$HOST:$REMOTE/models/tcm_so2_best_lane0.pt" \
  "$HOST:$REMOTE/models/tcm_so2_best_lane1.pt" \
  "$DEST/models/" 2>/dev/null || true

for log in pod_gpu_lane0.log pod_gpu_lane1.log pod_harbor_matrix.log pod_deep_matrix.log pod_dual_full.log pod_dual_matrix.out pod_dual_matrix.log pod_deep_launch.log; do
  scp -P "$PORT" -i "$KEY" -o StrictHostKeyChecking=no \
    "$HOST:/tmp/$log" "$DEST/logs/" 2>/dev/null || true
done

scp -P "$PORT" -i "$KEY" -o StrictHostKeyChecking=no -r \
  "$HOST:$REMOTE/artifacts/validation/20260712T200431Z-196d5d0" \
  "$DEST/validation/" 2>/dev/null || true

scp -P "$PORT" -i "$KEY" -o StrictHostKeyChecking=no -r \
  "$HOST:$REMOTE/artifacts/validation/20260712T231253Z-synced" \
  "$DEST/validation/" 2>/dev/null || true

cp -f "$DEST/models/tcm_so2.pt" "$LOCAL_ROOT/models/tcm_so2.pt" 2>/dev/null || true

{
  echo "fetch_time_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "host=$HOST port=$PORT"
  echo "--- models ---"
  ls -lh "$DEST/models" 2>/dev/null || true
  echo "--- logs ---"
  ls -lh "$DEST/logs" 2>/dev/null || true
  echo "--- validation ---"
  find "$DEST/validation" -maxdepth 3 -type d 2>/dev/null || true
  echo "--- local models/tcm_so2.pt ---"
  ls -lh "$LOCAL_ROOT/models/tcm_so2.pt" 2>/dev/null || true
} > "$DEST/MANIFEST.txt"

cat "$DEST/MANIFEST.txt"
