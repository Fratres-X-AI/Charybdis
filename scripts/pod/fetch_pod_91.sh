#!/usr/bin/env bash
set -euo pipefail

HOST=root@91.199.227.82
PORT=31640
KEY="${HOME}/.ssh/id_ed25519"
LOCAL_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REMOTE_ROOT=/workspace/Charybdis
STAMP=20260710T084153Z-3226290
REMOTE_ARTIFACT="${REMOTE_ROOT}/artifacts/validation/${STAMP}"
LOCAL_ARTIFACT="${LOCAL_ROOT}/artifacts/validation/${STAMP}"
LOCAL_LOGS="${LOCAL_ROOT}/artifacts/validation/${STAMP}/pod_logs"

mkdir -p "${LOCAL_ARTIFACT}" "${LOCAL_LOGS}"

echo "fetching validation artifacts..."
scp -P "$PORT" -i "$KEY" -r "${HOST}:${REMOTE_ARTIFACT}/." "${LOCAL_ARTIFACT}/"

echo "fetching pod logs..."
scp -P "$PORT" -i "$KEY" \
  "${HOST}:/tmp/pod_phase2.log" \
  "${HOST}:/tmp/pod_bootstrap.out" \
  "${LOCAL_LOGS}/"

echo "fetch_ok ${LOCAL_ARTIFACT}"
du -sh "${LOCAL_ARTIFACT}"
ls -la "${LOCAL_ARTIFACT}" | head -n 20
