#!/usr/bin/env bash
# Pull models + logs + validation dirs from H200 pod without stopping workers.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
DEST="${AWAY_PULL_DEST:-$LOCAL_ROOT/artifacts/pod_h200_live_pull}"
mkdir -p "$DEST/models" "$DEST/logs" "$DEST/validation"
STATE="$DEST/.pulled_validation_dirs"
touch "$STATE"

echo "=== H200 INCREMENTAL PULL $STAMP -> $DEST ==="

scp -o StrictHostKeyChecking=no -P "$POD_PORT" -i "$POD_KEY" -r \
  "$POD_HOST:/workspace/Charybdis/models/" "$DEST/" 2>/dev/null || true

mapfile -t REMOTE_DIRS < <(
  ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
    'ls -1d /workspace/Charybdis/artifacts/validation/* 2>/dev/null' || true
)

new=0
for remote in "${REMOTE_DIRS[@]}"; do
  [[ -z "$remote" ]] && continue
  base=$(basename "$remote")
  if grep -Fxq "$base" "$STATE" 2>/dev/null; then
    continue
  fi
  echo "pull validation/$base"
  scp -o StrictHostKeyChecking=no -P "$POD_PORT" -i "$POD_KEY" -r \
    "$POD_HOST:$remote" "$DEST/validation/" 2>/dev/null && {
    echo "$base" >>"$STATE"
    new=$((new + 1))
  } || echo "warn: failed $base"
done

for f in \
  pod_gpu_lane0.log pod_gpu_lane1.log \
  pod_h200_lane0.log pod_h200_lane1.log \
  pod_quad_gpu.out pod_quad_gpu.log \
  pod_h200_followon.log pod_h200_followon_stdout.log \
  pod_cpu_elite.log pod_cpu_elite_stdout.log \
  pod_hotzone_bathy.log pod_hotzone_bathy_stdout.log \
  pod_highres_bathy.log pod_post_train_full_pass.log \
  pod_full_pass.log; do
  scp -o StrictHostKeyChecking=no -P "$POD_PORT" -i "$POD_KEY" \
    "$POD_HOST:/tmp/$f" "$DEST/logs/" 2>/dev/null || true
done

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
  'cd /workspace/Charybdis && echo pod='"${POD_NAME}"' && git rev-parse HEAD && git log -1 --oneline && nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader 2>/dev/null' \
  > "$DEST/pod_state_${STAMP}.txt" 2>&1 || true

bash "$SCRIPT_DIR/gpu_progress.sh" > "$DEST/logs/gpu_progress_${STAMP}.txt" 2>&1 || true

echo "H200_INCREMENTAL_PULL new_validation_dirs=$new dest=$DEST"
du -sh "$DEST" 2>/dev/null || true
