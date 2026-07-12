#!/usr/bin/env bash
set -euo pipefail
HOST=root@213.192.2.94
PORT=40077
KEY="${HOME}/.ssh/id_ed25519"
LOCAL_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAMP=20260712T175513Z-10869ea
PULL_ROOT="${LOCAL_ROOT}/artifacts/pod_pull_20260712"
LOG_DIR="${PULL_ROOT}/logs"
MODEL_DIR="${PULL_ROOT}/models"
VAL_DIR="${PULL_ROOT}/validation/${STAMP}"

mkdir -p "$LOG_DIR" "$MODEL_DIR" "$VAL_DIR"

echo "fetch validation artifacts..."
scp -P "$PORT" -i "$KEY" -r "${HOST}:/workspace/Charybdis/artifacts/validation/${STAMP}/." "${VAL_DIR}/" 2>/dev/null || true

echo "fetch models..."
scp -P "$PORT" -i "$KEY" "${HOST}:/workspace/Charybdis/models/tcm_so2"*.pt "${MODEL_DIR}/" 2>/dev/null || true

echo "fetch logs..."
for f in pod_sprint.log pod_sprint.out pod_max_gpu.log pod_max_gpu.out nn_eval.log; do
  scp -P "$PORT" -i "$KEY" "${HOST}:/tmp/${f}" "${LOG_DIR}/" 2>/dev/null || true
done
scp -P "$PORT" -i "$KEY" "${HOST}:/workspace/Charybdis/ten_pass.log" "${LOG_DIR}/" 2>/dev/null || true

echo "write summary..."
ssh -p "$PORT" -i "$KEY" "$HOST" 'grep "eval pass" /tmp/pod_max_gpu.log 2>/dev/null; grep "new_best" /tmp/pod_max_gpu.log 2>/dev/null; tail -n 8 /tmp/pod_max_gpu.log 2>/dev/null' > "${PULL_ROOT}/gpu_summary.txt" || true

echo "pull_ok ${PULL_ROOT}"
du -sh "${PULL_ROOT}"/* 2>/dev/null || du -sh "${PULL_ROOT}"
