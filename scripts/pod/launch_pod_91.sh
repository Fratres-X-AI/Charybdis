#!/usr/bin/env bash
set -euo pipefail

HOST=root@91.199.227.82
PORT=31640
KEY="${HOME}/.ssh/id_ed25519"
LOCAL="$(cd "$(dirname "$0")" && pwd)/pod_bootstrap_91.sh"

scp -P "$PORT" -i "$KEY" "$LOCAL" "${HOST}:/tmp/pod_bootstrap.sh"
ssh -p "$PORT" -i "$KEY" "$HOST" 'sed -i "s/\r$//" /tmp/pod_bootstrap.sh; chmod +x /tmp/pod_bootstrap.sh; nohup /tmp/pod_bootstrap.sh > /tmp/pod_bootstrap.out 2>&1 & echo started'
