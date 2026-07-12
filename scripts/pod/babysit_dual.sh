#!/usr/bin/env bash
# Autonomous 4h babysit: poll every 90s, fix and relaunch on failure.
set -euo pipefail
HOST=root@157.157.221.29
PORT=30511
KEY="${HOME}/.ssh/id_ed25519"
REPO=/workspace/Charybdis
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG="$ROOT/artifacts/pod_babysit.log"
mkdir -p "$(dirname "$LOG")"
END=$((SECONDS + 14400))

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

ssh_pod() {
  ssh -p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=15 "$HOST" "$@"
}

restart_gpu() {
  log "ACTION restart dual GPU"
  ssh_pod "bash -s" < "$(dirname "$0")/go_gpu_now.sh" >>"$LOG" 2>&1 || log "WARN gpu restart failed"
}

resume_phase2_gpu() {
  log "ACTION resume phase2+gpu"
  ssh_pod "bash -s" < "$(dirname "$0")/launch_phase2_gpu_remote.sh" >>"$LOG" 2>&1 || log "WARN phase2 resume failed"
}

poll_once() {
  ssh_pod bash -s <<'REMOTE'
ts() { date -u +"%H:%M:%S"; }
echo "POLL_TIME=$(ts)"
echo "CPUS=$(nproc)"
echo "PY=$(pgrep -c python 2>/dev/null || echo 0)"
pgrep -af "pod_dual|hybrid_validate|phase1|pod_max_gpu|go_gpu|pip install" || echo "NO_PROCS"
echo "GPU_STAT=$(nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader 2>/dev/null | tr '\n' ';')"
tail -n 2 /tmp/gpu_go.out 2>/dev/null || true
tail -n 2 /tmp/pod_gpu_lane0.log 2>/dev/null || true
tail -n 2 /tmp/pod_gpu_lane1.log 2>/dev/null || true
tail -n 2 /tmp/pod_dual_gpu_retry.out 2>/dev/null || true
grep -E "PASS |FAIL |FINAL|new_best|PHASE|gpu_restarted|torch_ok" /tmp/pod_dual_full.log 2>/dev/null | tail -n 3 || true
REMOTE
}

log "BABYSIT START 4h cycle every 90s"
i=0
while (( SECONDS < END )); do
  i=$((i + 1))
  log "=== poll $i ==="
  OUT="$(poll_once 2>&1 || echo POLL_FAILED)"
  echo "$OUT" >>"$LOG"

  if echo "$OUT" | grep -q "NO_PROCS"; then
    if echo "$OUT" | grep -q "pod_max_gpu_lane\|pod_dual_gpu_max\|go_gpu_now"; then
      log "GPU install/train bash active — skip relaunch"
    elif echo "$OUT" | grep -q "HARBOR_RELEASE_DONE\|deep_release\|PHASE2"; then
      restart_gpu
    elif echo "$OUT" | grep -q "PHASE1_DONE\|Phase 1 pod acceptance passed"; then
      resume_phase2_gpu
    else
      log "ACTION full relaunch"
      bash "$SCRIPT_DIR/launch_dual_full.sh" >>"$LOG" 2>&1 || true
    fi
  fi

  if echo "$OUT" | grep -qi "FINAL.*after_mean"; then
    if ! echo "$OUT" | grep -q "pod_max_gpu_lane"; then
      log "GPU lanes may be complete — checking promotion"
      restart_gpu
    fi
  fi

  if echo "$OUT" | grep -q "POLL_FAILED"; then
    log "WARN ssh poll failed"
  fi

  sleep 90
done
log "BABYSIT END 4h complete"
