#!/usr/bin/env bash
set -euo pipefail

HOST="${POD_HOST:-root@64.247.206.218}"
PORT="${POD_PORT:-14049}"
KEY="${POD_KEY:-${HOME}/.ssh/id_ed25519}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

scp -P "${PORT}" -i "${KEY}" \
  "${ROOT}/scripts/pod/phase1_pod.sh" \
  "${HOST}:/workspace/Charybdis/scripts/pod/phase1_pod.sh"
ssh -p "${PORT}" -i "${KEY}" -o BatchMode=yes -T "${HOST}" \
  "sed -i 's/\r$//' /workspace/Charybdis/scripts/pod/phase1_pod.sh; chmod +x /workspace/Charybdis/scripts/pod/phase1_pod.sh"
