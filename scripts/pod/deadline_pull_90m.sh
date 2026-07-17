#!/usr/bin/env bash
# Pull at green OR +95 minutes.
# Credit math: ~$17.50 / $8.81/hr ≈ 119 minutes left — keep ~20m buffer before empty.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=scripts/pod/pod_env.sh
source "$SCRIPT_DIR/pod_env.sh"

MAX_MINUTES="${MAX_MINUTES:-95}"
INTERVAL=90
START=$(date +%s)
DEADLINE=$((START + MAX_MINUTES * 60))
LOG="$LOCAL_ROOT/artifacts/deadline_credit_safe.log"
mkdir -p "$LOCAL_ROOT/artifacts"

echo "=== CREDIT-SAFE PULL +${MAX_MINUTES}m from $(date -u +%H:%M:%SZ) pod=${POD_NAME} ===" | tee "$LOG"
echo "Pull before RunPod balance hits zero. Incremental every ~10m." | tee -a "$LOG"

while true; do
  now=$(date +%s)
  left_m=$(( (DEADLINE - now) / 60 ))
  echo "" | tee -a "$LOG"
  echo "==== left=${left_m}m $(date -u +%H:%M:%SZ) ====" | tee -a "$LOG"

  set +e
  bash "$SCRIPT_DIR/pod_pipeline_green.sh" --report 2>&1 | tee -a "$LOG"
  rc=$?
  set -e

  if (( rc == 0 )); then
    echo "GREEN — final pull" | tee -a "$LOG"
    bash "$SCRIPT_DIR/pull_h200_shutdown.sh" 2>&1 | tee -a "$LOG"
    echo "PULL_DONE reason=green STOP_POD_OK" | tee -a "$LOG"
    exit 0
  fi

  if (( now >= DEADLINE )); then
    echo "CREDIT SAFETY — force full pull" | tee -a "$LOG"
    bash "$SCRIPT_DIR/pull_h200_shutdown.sh" 2>&1 | tee -a "$LOG" || true
    echo "PULL_DONE reason=credit_buffer STOP_POD_OK" | tee -a "$LOG"
    exit 0
  fi

  elapsed=$(( now - START ))
  if (( elapsed > 0 && elapsed % 600 < INTERVAL )); then
    bash "$SCRIPT_DIR/pull_h200_incremental.sh" 2>&1 | tee -a "$LOG" || true
  fi

  sleep "$INTERVAL"
done
