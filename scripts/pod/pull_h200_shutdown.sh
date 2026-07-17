#!/usr/bin/env bash
# Full pull from H200 pod before shutdown — models, validation, all lane logs.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
DEST="$LOCAL_ROOT/artifacts/pod_h200_final_${STAMP}"
mkdir -p "$DEST/models" "$DEST/logs" "$DEST/validation"

echo "=== H200 SHUTDOWN PULL $STAMP -> $DEST ==="
echo "pod=${POD_NAME} host=${POD_HOST}:${POD_PORT}"

echo "=== remote snapshot ==="
bash "$SCRIPT_DIR/gpu_progress.sh" | tee "$DEST/logs/gpu_progress_final.txt" || true

echo "=== models ==="
scp -o StrictHostKeyChecking=no -P "$POD_PORT" -i "$POD_KEY" -r \
  "$POD_HOST:/workspace/Charybdis/models/" "$DEST/" 2>/dev/null || true

echo "=== validation (full tree) ==="
scp -o StrictHostKeyChecking=no -P "$POD_PORT" -i "$POD_KEY" -r \
  "$POD_HOST:/workspace/Charybdis/artifacts/validation/" "$DEST/" 2>/dev/null || true

echo "=== logs ==="
for f in \
  pod_gpu_lane0.log pod_gpu_lane1.log \
  pod_h200_lane0.log pod_h200_lane1.log \
  pod_quad_gpu.out pod_quad_gpu.log \
  pod_h200_followon.log pod_h200_followon_stdout.log \
  pod_cpu_elite.log pod_cpu_elite_stdout.log \
  pod_cpu_mission.log pod_cpu_holdout_h.log pod_cpu_holdout_d.log \
  pod_cpu_harbor_rel.log pod_cpu_deep_rel.log \
  pod_hotzone_bathy.log pod_hotzone_bathy_stdout.log \
  pod_highres_bathy.log pod_post_train_full_pass.log \
  pod_full_pass.log pod_full_pass_stdout.log; do
  scp -o StrictHostKeyChecking=no -P "$POD_PORT" -i "$POD_KEY" \
    "$POD_HOST:/tmp/$f" "$DEST/logs/" 2>/dev/null || true
done

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
  'cd /workspace/Charybdis && echo pod='"${POD_NAME}"' && git rev-parse HEAD && git log -1 --oneline && ls -lh models/tcm_so2*.pt 2>/dev/null' \
  > "$DEST/git_state.txt" 2>&1 || true

echo "H200_SHUTDOWN_PULL_COMPLETE dest=$DEST"
du -sh "$DEST" "$DEST"/* 2>/dev/null || true
find "$DEST" -type f | wc -l | xargs -I{} echo "files={}"
