#!/usr/bin/env bash
set -euo pipefail
HOST=root@213.192.2.94
PORT=40077
KEY="${HOME}/.ssh/id_ed25519"
LOCAL_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAMP=20260712T175513Z-10869ea
REMOTE_ARTIFACT="/workspace/Charybdis/artifacts/validation/${STAMP}"
LOCAL_ARTIFACT="${LOCAL_ROOT}/artifacts/validation/${STAMP}"
LOCAL_LOGS="${LOCAL_ARTIFACT}/pod_logs"

mkdir -p "${LOCAL_ARTIFACT}" "${LOCAL_LOGS}"
scp -P "$PORT" -i "$KEY" -r "${HOST}:${REMOTE_ARTIFACT}/." "${LOCAL_ARTIFACT}/"
scp -P "$PORT" -i "$KEY" \
  "${HOST}:/tmp/pod_sprint.log" \
  "${HOST}:/tmp/pod_sprint.out" \
  "${LOCAL_LOGS}/"
echo "fetch_ok ${LOCAL_ARTIFACT}"
