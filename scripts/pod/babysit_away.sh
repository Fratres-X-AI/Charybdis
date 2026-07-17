#!/usr/bin/env bash
# Away-mode watcher: incremental pulls + heal until 100% pipeline green.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

INTERVAL="${AWAY_PULL_SEC:-300}"
MAX_HOURS="${AWAY_MAX_HOURS:-12}"
MAX_LOOPS=$((MAX_HOURS * 3600 / INTERVAL))
LOG="$LOCAL_ROOT/artifacts/away_watch.log"
FINAL_DEST="$LOCAL_ROOT/artifacts/pod_h200_final_$(date -u +%Y%m%dT%H%M%SZ)"

REMOTE_GPU_COUNT="$(ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" 'nvidia-smi -L 2>/dev/null | wc -l' 2>/dev/null || echo 2)"
GPU_TARGET="${GPU_TARGET:-$REMOTE_GPU_COUNT}"
if ! [[ "$GPU_TARGET" =~ ^[0-9]+$ ]] || (( GPU_TARGET < 1 )); then
  GPU_TARGET=2
fi
export GPU_TARGET

log() { echo "[$(date -u +%H:%M:%SZ)] $*" | tee -a "$LOG"; }

log "AWAY_WATCH_START pod=${POD_NAME} interval=${INTERVAL}s max_hours=${MAX_HOURS} gpu_lanes=${GPU_TARGET}"
bash "$SCRIPT_DIR/pod_heal_h200.sh" >>"$LOG" 2>&1 || log "WARN initial heal failed"

loop=0
while (( loop < MAX_LOOPS )); do
  loop=$((loop + 1))
  log "=== away loop $loop/$MAX_LOOPS ==="
  bash "$SCRIPT_DIR/pull_h200_incremental.sh" >>"$LOG" 2>&1 || log "WARN incremental pull failed"
  bash "$SCRIPT_DIR/gpu_progress.sh" >>"$LOG" 2>&1 || true

  if (( loop % 3 == 0 )); then
    bash "$SCRIPT_DIR/pod_heal_h200.sh" >>"$LOG" 2>&1 || log "WARN heal failed"
  fi

  set +e
  bash "$SCRIPT_DIR/pod_pipeline_green.sh" --report >>"$LOG" 2>&1
  green_rc=$?
  set -e
  log "pipeline_green=${green_rc}"

  if (( green_rc == 0 )); then
    log "100% GREEN — final pull -> $FINAL_DEST"
    AWAY_PULL_DEST="$FINAL_DEST" bash "$SCRIPT_DIR/pull_h200_shutdown.sh" >>"$LOG" 2>&1 || true
    log "AWAY_WATCH_DONE final=$FINAL_DEST"
    exit 0
  fi

  sleep "$INTERVAL"
done

log "AWAY_WATCH_TIMEOUT — partial pull"
bash "$SCRIPT_DIR/pull_h200_shutdown.sh" >>"$LOG" 2>&1 || true
log "AWAY_WATCH_END (timeout)"
exit 1
