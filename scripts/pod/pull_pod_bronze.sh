#!/usr/bin/env bash
# Pull all bronze pod validation artifacts and logs (full teardown pull).
set -euo pipefail
HOST=root@213.173.107.32
PORT=37613
KEY="${HOME}/.ssh/id_ed25519"
LOCAL_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAMP="${1:-20260714}"
PULL_ROOT="${LOCAL_ROOT}/artifacts/pod_bronze_pull_${STAMP}"
VAL_DIR="${PULL_ROOT}/validation"
LOG_DIR="${PULL_ROOT}/logs"

mkdir -p "$VAL_DIR" "$LOG_DIR"

pull_tree() {
  local remote_stamp="$1"
  local local_name="$2"
  echo "fetch ${remote_stamp} -> ${local_name}..."
  mkdir -p "${VAL_DIR}/${local_name}"
  scp -P "$PORT" -i "$KEY" -o StrictHostKeyChecking=no -r \
    "${HOST}:/workspace/Charybdis/artifacts/validation/${remote_stamp}/." \
    "${VAL_DIR}/${local_name}/"
}

pull_tree "20260714T153106Z-ad7fa3e" "phase2_complete"
pull_tree "20260714T155620Z-ad7fa3e/beach_max" "beach_max"

echo "fetch logs..."
for f in pod_bronze_military.log pod_harbor_engineering.log pod_deep_engineering.log \
         pod_harbor_release.log pod_deep_release.log pod_bronze_beach.log \
         pod_bronze_beach_stdout.log pod_beach_harbor.log pod_beach_deep.log; do
  scp -P "$PORT" -i "$KEY" -o StrictHostKeyChecking=no \
    "${HOST}:/tmp/${f}" "${LOG_DIR}/" 2>/dev/null || true
done

echo "pull_ok ${PULL_ROOT}"
find "${PULL_ROOT}" -type f | wc -l
du -sh "${PULL_ROOT}" "${PULL_ROOT}"/* 2>/dev/null || true
