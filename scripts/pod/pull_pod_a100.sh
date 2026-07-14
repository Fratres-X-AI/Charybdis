#!/usr/bin/env bash
# Pull A100 pod validation artifacts, models, and logs.
set -euo pipefail
HOST=root@195.26.233.70
PORT=55580
KEY="${HOME}/.ssh/id_ed25519"
LOCAL_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAMP="${1:-20260714}"
PULL_ROOT="${LOCAL_ROOT}/artifacts/pod_a100_pull_${STAMP}"
VAL_DIR="${PULL_ROOT}/validation"
MODEL_DIR="${PULL_ROOT}/models"
LOG_DIR="${PULL_ROOT}/logs"

mkdir -p "$VAL_DIR" "$MODEL_DIR" "$LOG_DIR"

echo "fetch validation artifacts..."
scp -P "$PORT" -i "$KEY" -o StrictHostKeyChecking=no -r \
  "${HOST}:/workspace/Charybdis/artifacts/validation/20260714T124300Z-594f4e9/." \
  "${VAL_DIR}/deep_engineering/" 2>/dev/null || true
scp -P "$PORT" -i "$KEY" -o StrictHostKeyChecking=no -r \
  "${HOST}:/workspace/Charybdis/artifacts/validation/20260714T124447Z-594f4e9/." \
  "${VAL_DIR}/deep_release/" 2>/dev/null || true
scp -P "$PORT" -i "$KEY" -o StrictHostKeyChecking=no -r \
  "${HOST}:/workspace/Charybdis/artifacts/validation/20260714T120829Z-39732b9/engineering/." \
  "${VAL_DIR}/harbor_engineering/" 2>/dev/null || true

echo "fetch models..."
scp -P "$PORT" -i "$KEY" -o StrictHostKeyChecking=no \
  "${HOST}:/workspace/Charybdis/models/tcm_so2"*.pt \
  "${MODEL_DIR}/" 2>/dev/null || true

echo "fetch logs..."
for f in pod_deep_matrix.log pod_deep_release.log pod_gpu_lane0.log pod_harbor_matrix.log; do
  scp -P "$PORT" -i "$KEY" -o StrictHostKeyChecking=no \
    "${HOST}:/tmp/${f}" "${LOG_DIR}/" 2>/dev/null || true
done

echo "pull_ok ${PULL_ROOT}"
du -sh "${PULL_ROOT}"/* 2>/dev/null || true
