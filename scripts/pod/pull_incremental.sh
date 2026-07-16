#!/usr/bin/env bash
# Pull new validation artifacts + logs WITHOUT stopping pod workers.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

STAMP="${1:-$(date -u +%Y%m%dT%H%M%SZ)}"
DEST="$LOCAL_ROOT/artifacts/pod_elite_pull_${STAMP}"
STATE="$DEST/.pulled_dirs"
mkdir -p "$DEST/validation" "$DEST/logs"
touch "$STATE"

echo "=== incremental pull -> $DEST ==="

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
  echo "pull $base"
  scp -o StrictHostKeyChecking=no -P "$POD_PORT" -i "$POD_KEY" -r \
    "$POD_HOST:$remote" "$DEST/validation/" 2>/dev/null && {
    echo "$base" >>"$STATE"
    new=$((new + 1))
  } || echo "warn: failed $base"
done

for f in \
  pod_elite_phase34.log pod_elite_phase34_stdout.log \
  pod_phase2.log pod_elite_deep_eng.log pod_elite_deep_rel.log \
  pod_highres_bathy.log pod_mission_matrix.log pod_worst_sweep.log \
  pod_worst_harbor_rel.log pod_worst_deep_rel.log \
  pod_integration_grade.log pod_release_grade_stdout.log \
  pod_quad_gpu.log pod_gpu_lane0.log pod_gpu_lane1.log pod_gpu_lane2.log pod_gpu_lane3.log \
  pod_quad_cluster.log pod_quad_cluster_stdout.log \
  cluster0.log cluster1.log cluster2.log cluster3.log \
  pod_max_out.log pod_max_out_stdout.log \
  pod_int_harbor.log pod_int_deep.log \
  pod_rel_harbor.log pod_rel_deep.log pod_worst_harbor.log pod_worst_deep.log; do
  scp -o StrictHostKeyChecking=no -P "$POD_PORT" -i "$POD_KEY" \
    "$POD_HOST:/tmp/$f" "$DEST/logs/" 2>/dev/null || true
done

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
  'cd /workspace/Charybdis && echo pod='"${POD_NAME}"' && git rev-parse HEAD && git log -1 --oneline' \
  > "$DEST/git_state.txt" 2>&1 || true

if [[ -d "$DEST/validation/validation" ]]; then
  shopt -s dotglob
  mv "$DEST/validation/validation"/* "$DEST/validation/" 2>/dev/null || true
  rmdir "$DEST/validation/validation" 2>/dev/null || true
fi

echo "INCREMENTAL_PULL new_dirs=$new dest=$DEST"
du -sh "$DEST" 2>/dev/null || true
grep -q 'ELITE_PHASE34_COMPLETE' "$DEST/logs/pod_elite_phase34.log" 2>/dev/null && echo "REMOTE_COMPLETE=1" || echo "REMOTE_COMPLETE=0"
