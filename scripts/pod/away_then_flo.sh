#!/usr/bin/env bash
# Away mode for Charybdis → credit-safe pull → optional FLO-DRC handoff if time left.
#
# Credit: ~$17.50 @ ~$8.81/hr ≈ 119 minutes from when balance was reported.
# We keep a buffer and only start FLO if MIN_FLO_MINUTES remain after Charybdis pull.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CHARYBDIS_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
FLO_ROOT="${FLO_ROOT:-/c/Users/Besn Daddy/Desktop/FLO-DRC}"
# shellcheck source=scripts/pod/pod_env.sh
source "$SCRIPT_DIR/pod_env.sh"

# Minutes from THIS script start until forced Charybdis pull
CHARYBDIS_MAX_MIN="${CHARYBDIS_MAX_MIN:-95}"
# Need at least this many minutes left (vs hard credit wall) to launch FLO
MIN_FLO_MINUTES="${MIN_FLO_MINUTES:-25}"
# Absolute credit wall from script start (don't run FLO past this)
CREDIT_WALL_MIN="${CREDIT_WALL_MIN:-115}"

INTERVAL=90
START=$(date +%s)
CHARYBDIS_DEADLINE=$((START + CHARYBDIS_MAX_MIN * 60))
CREDIT_WALL=$((START + CREDIT_WALL_MIN * 60))
LOG="$CHARYBDIS_ROOT/artifacts/away_then_flo.log"
mkdir -p "$CHARYBDIS_ROOT/artifacts"

echo "=== AWAY THEN FLO ===" | tee "$LOG"
echo "charybdis_pull_by=+${CHARYBDIS_MAX_MIN}m credit_wall=+${CREDIT_WALL_MIN}m flo_min=${MIN_FLO_MINUTES}m" | tee -a "$LOG"
echo "flo_root=$FLO_ROOT" | tee -a "$LOG"

charybdis_pulled=0
while true; do
  now=$(date +%s)
  left_c=$(( (CHARYBDIS_DEADLINE - now) / 60 ))
  left_w=$(( (CREDIT_WALL - now) / 60 ))
  echo "" | tee -a "$LOG"
  echo "==== charybdis left=${left_c}m credit_wall=${left_w}m $(date -u +%H:%M:%SZ) ====" | tee -a "$LOG"

  set +e
  bash "$SCRIPT_DIR/pod_pipeline_green.sh" --report 2>&1 | tee -a "$LOG"
  rc=$?
  set -e

  if (( rc == 0 )); then
    echo "CHARYBDIS GREEN — final pull" | tee -a "$LOG"
    bash "$SCRIPT_DIR/pull_h200_shutdown.sh" 2>&1 | tee -a "$LOG"
    charybdis_pulled=1
    echo "CHARYBDIS_PULL_DONE reason=green" | tee -a "$LOG"
    break
  fi

  if (( now >= CHARYBDIS_DEADLINE )); then
    echo "CHARYBDIS DEADLINE — force pull" | tee -a "$LOG"
    bash "$SCRIPT_DIR/pull_h200_shutdown.sh" 2>&1 | tee -a "$LOG" || true
    charybdis_pulled=1
    echo "CHARYBDIS_PULL_DONE reason=deadline" | tee -a "$LOG"
    break
  fi

  elapsed=$(( now - START ))
  if (( elapsed > 0 && elapsed % 600 < INTERVAL )); then
    bash "$SCRIPT_DIR/pull_h200_incremental.sh" 2>&1 | tee -a "$LOG" || true
  fi

  # Light heal that won't thrash CPU if already green
  bash "$SCRIPT_DIR/pod_heal_h200.sh" 2>&1 | tee -a "$LOG" || true

  sleep "$INTERVAL"
done

now=$(date +%s)
left_for_flo=$(( (CREDIT_WALL - now) / 60 ))
echo "after_charybdis minutes_to_credit_wall=${left_for_flo}" | tee -a "$LOG"

# FLO-DRC is CPU-primary — do NOT keep an H200 burning for it.
# Run FLO later on a cheap CPU pod or locally.
SKIP_FLO_ON_H200="${SKIP_FLO_ON_H200:-1}"
if [[ "$SKIP_FLO_ON_H200" == "1" ]]; then
  echo "SKIP FLO on H200 — CPU-only workload; stop expensive pod after Charybdis pull" | tee -a "$LOG"
  echo "STOP_POD_OK charybdis_pulled=${charybdis_pulled} flo=deferred_cpu" | tee -a "$LOG"
  exit 0
fi

if (( left_for_flo < MIN_FLO_MINUTES )); then
  echo "SKIP FLO — not enough credit time (need ${MIN_FLO_MINUTES}m, have ${left_for_flo}m)" | tee -a "$LOG"
  echo "STOP_POD_OK charybdis_pulled=${charybdis_pulled} flo=skipped" | tee -a "$LOG"
  exit 0
fi

if [[ ! -d "$FLO_ROOT/scripts/pod" ]]; then
  echo "SKIP FLO — missing $FLO_ROOT" | tee -a "$LOG"
  echo "STOP_POD_OK charybdis_pulled=${charybdis_pulled} flo=missing_repo" | tee -a "$LOG"
  exit 0
fi

echo "=== HANDOFF TO FLO-DRC (${left_for_flo}m credit left) ===" | tee -a "$LOG"

# Sync current Direct TCP creds into FLO local env
mkdir -p "$FLO_ROOT/scripts/pod"
cat > "$FLO_ROOT/scripts/pod/pod_env.local.sh" <<EOF
#!/usr/bin/env bash
export POD_NAME="${POD_NAME}"
export POD_HOST="${POD_HOST}"
export POD_PORT="${POD_PORT}"
export POD_KEY="${POD_KEY}"
EOF

# Wait until Charybdis GPU workers are gone (or timeout) — do not kill them here if still finishing
if [[ -x "$FLO_ROOT/scripts/pod/wait_charybdis_clear.sh" ]]; then
  MAX_HOURS=0.25 bash "$FLO_ROOT/scripts/pod/wait_charybdis_clear.sh" 2>&1 | tee -a "$LOG" || true
fi

# Soft-stop Charybdis trainers so FLO can use CPUs; keep pod alive
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
  'pkill -f "pod_h200_max_gpu_lane|pod_max_gpu_lane|pod_h200_followon|pod_quad_gpu|pod_cpu_elite|pod_hotzone|pod_full_pass|hybrid_validate" 2>/dev/null || true; sleep 2; echo CHARYBDIS_WORKERS_CLEARED; nvidia-smi --query-gpu=index,memory.used --format=csv,noheader' \
  2>&1 | tee -a "$LOG" || true

cd "$FLO_ROOT"
chmod +x scripts/pod/*.sh 2>/dev/null || true
# Cap FLO babysit to remaining credit wall minus 5m buffer
FLO_MAX=$(( left_for_flo - 5 ))
if (( FLO_MAX < 10 )); then
  echo "SKIP FLO — FLO_MAX too small (${FLO_MAX}m)" | tee -a "$LOG"
  echo "STOP_POD_OK charybdis_pulled=1 flo=skipped_small_window" | tee -a "$LOG"
  exit 0
fi

echo "Launching FLO go_h200.sh with GPU_MAX_HOURS≈$(( FLO_MAX / 60 )) (cap ${FLO_MAX}m)" | tee -a "$LOG"
# FLO training is CPU-primary; go_h200 still preflights H200s
export GPU_MAX_HOURS=1
export GPU_POLL_SEC=90
set +e
bash scripts/pod/go_h200.sh 2>&1 | tee -a "$LOG"
flo_rc=$?
set -e
echo "FLO_DONE rc=${flo_rc}" | tee -a "$LOG"
echo "STOP_POD_OK charybdis_pulled=1 flo_rc=${flo_rc}" | tee -a "$LOG"
exit "$flo_rc"
