#!/usr/bin/env bash
# Fail fast if pod SSH is unreachable or GPUs are missing.
# For 2x H200 SXM runs, require at least 2 visible GPUs.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/pod/pod_env.sh
source "$SCRIPT_DIR/pod_env.sh"

MIN_GPUS="${MIN_GPUS:-2}"
REQUIRE_H200="${REQUIRE_H200:-0}"

echo "=== POD PREFLIGHT pod=${POD_NAME} host=${POD_HOST}:${POD_PORT} ==="

if [[ "$POD_HOST" == *"0.0.0.0"* ]] \
  || [[ "$POD_HOST" == *"REPLACE"* ]] \
  || [[ "$POD_NAME" == "replace_me" ]] \
  || [[ "$POD_NAME" == "REPLACE_WHEN_POD_IS_UP" ]]; then
  echo "ERROR: Configure scripts/pod/pod_env.local.sh with Direct TCP SSH from RunPod."
  echo "  cp scripts/pod/pod_env.local.sh.example scripts/pod/pod_env.local.sh"
  echo "  # edit POD_NAME / POD_HOST / POD_PORT from Connect → SSH over exposed TCP"
  exit 1
fi

set +e
out=$(ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
  'echo SSH_OK; nvidia-smi -L; nvidia-smi --query-gpu=name,memory.total --format=csv,noheader' 2>&1)
rc=$?
set -e
echo "$out"

if (( rc != 0 )); then
  echo ""
  echo "ERROR: Cannot reach pod. Pod may be stopped or IP/port changed after restart."
  echo "  Update scripts/pod/pod_env.local.sh with fresh Direct TCP SSH, then re-run."
  exit 1
fi

ngpu=$(echo "$out" | grep -c '^GPU ' || true)
if (( ngpu < MIN_GPUS )); then
  echo "ERROR: need >= ${MIN_GPUS} GPUs, found ${ngpu}"
  exit 1
fi

if [[ "$REQUIRE_H200" == "1" ]] && ! echo "$out" | grep -qi 'H200'; then
  echo "ERROR: REQUIRE_H200=1 but no H200 in nvidia-smi inventory"
  exit 1
fi

if echo "$out" | grep -qi 'H200'; then
  echo "GPU_TARGET=H200_SXM count=${ngpu}"
fi

echo "PREFLIGHT_OK"
