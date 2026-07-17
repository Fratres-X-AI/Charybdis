#!/usr/bin/env bash
# Hard deadline pull — run in parallel with babysit. Pulls at green OR at MAX_MINUTES.
# Usage: MAX_MINUTES=110 bash scripts/pod/deadline_pull_2h.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=scripts/pod/pod_env.sh
source "$SCRIPT_DIR/pod_env.sh"

MAX_MINUTES="${MAX_MINUTES:-110}"
INTERVAL="${DEADLINE_POLL_SEC:-90}"
START=$(date +%s)
DEADLINE=$((START + MAX_MINUTES * 60))
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
LOG="$LOCAL_ROOT/artifacts/deadline_2h_${STAMP}.log"
mkdir -p "$LOCAL_ROOT/artifacts"

echo "=== DEADLINE PULL max=${MAX_MINUTES}m pod=${POD_NAME} ===" | tee "$LOG"

pulled=0
while true; do
  now=$(date +%s)
  left=$(( (DEADLINE - now) / 60 ))
  echo "" | tee -a "$LOG"
  echo "==== deadline poll left=${left}m $(date -u +%H:%M:%SZ) ====" | tee -a "$LOG"

  set +e
  bash "$SCRIPT_DIR/pod_pipeline_green.sh" --report 2>&1 | tee -a "$LOG"
  rc=$?
  set -e

  if (( rc == 0 )); then
    echo "GREEN before deadline — final pull" | tee -a "$LOG"
    bash "$SCRIPT_DIR/pull_h200_shutdown.sh" 2>&1 | tee -a "$LOG"
    pulled=1
    echo "DEADLINE_PULL_DONE reason=green" | tee -a "$LOG"
    exit 0
  fi

  if (( now >= DEADLINE )); then
    echo "DEADLINE HIT — force pull (not all green)" | tee -a "$LOG"
    bash "$SCRIPT_DIR/pull_h200_shutdown.sh" 2>&1 | tee -a "$LOG" || true
    pulled=1
    echo "DEADLINE_PULL_DONE reason=timeout left_gates_red" | tee -a "$LOG"
    exit 1
  fi

  # Mid-run incremental safety pull every ~15 min
  elapsed=$(( now - START ))
  if (( elapsed > 0 && elapsed % 900 < INTERVAL )); then
    bash "$SCRIPT_DIR/pull_h200_incremental.sh" 2>&1 | tee -a "$LOG" || true
  fi

  sleep "$INTERVAL"
done
