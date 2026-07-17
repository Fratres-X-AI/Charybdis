#!/usr/bin/env bash
# Restart local babysit if dead; never kill remote GPU work.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
# shellcheck source=scripts/pod/pod_env.sh
source scripts/pod/pod_env.sh

LOG="$ROOT/artifacts/go_h200_sxm.log"
mkdir -p "$ROOT/artifacts"

alive=0
if ps -ef 2>/dev/null | grep -E 'babysit_h200_elite|go_h200_sxm' | grep -v grep >/dev/null; then
  alive=1
fi
# Windows Git Bash may not show ps the same way — also check for recent log growth
if [[ -f "$LOG" ]]; then
  age=$(( $(date +%s) - $(stat -c %Y "$LOG" 2>/dev/null || stat -f %m "$LOG") ))
  echo "log_age_s=$age"
  if (( age < 180 )); then
    alive=1
  fi
fi

echo "babysit_alive=$alive"
if (( alive == 0 )); then
  echo "RESTART babysit_h200_elite (remote lanes left alone)"
  nohup bash scripts/pod/babysit_h200_elite.sh >>"$LOG" 2>&1 &
  echo "babysit_pid=$!"
fi

ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set +e
cd /workspace/Charybdis
echo "=== remote health ==="
nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader
echo "lanes=$(pgrep -c -f 'pod_max_gpu_lane.sh' || echo 0) followon=$(pgrep -c -f pod_h200_followon || echo 0) cpu=$(pgrep -c -f hybrid_validate || echo 0)"
# If GPU lanes died mid round-1, heal
r1=0
grep -qE 'FINAL gpu=0\b' /tmp/pod_gpu_lane0.log 2>/dev/null && r1=$((r1+1))
grep -qE 'FINAL gpu=1\b' /tmp/pod_gpu_lane1.log 2>/dev/null && r1=$((r1+1))
echo "r1_final=$r1/2"
if (( r1 < 2 )) && ! pgrep -f 'pod_max_gpu_lane.sh' >/dev/null; then
  echo "HEAL launching pod_quad_gpu_max"
  nohup bash scripts/pod/pod_quad_gpu_max.sh > /tmp/pod_quad_gpu.out 2>&1 &
fi
if ! pgrep -f pod_h200_followon >/dev/null; then
  echo "HEAL launching followon"
  nohup bash scripts/pod/pod_h200_followon.sh > /tmp/pod_h200_followon_stdout.log 2>&1 &
fi
tail -2 /tmp/pod_gpu_lane0.log 2>/dev/null
tail -2 /tmp/pod_gpu_lane1.log 2>/dev/null
REMOTE
