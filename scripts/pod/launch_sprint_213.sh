#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
HOST=root@213.192.2.94
PORT=40077
KEY="${HOME}/.ssh/id_ed25519"

bash "$ROOT/sync_pod_213.sh"
scp -P "$PORT" -i "$KEY" "$ROOT/pod_sprint_213.sh" "${HOST}:/tmp/pod_sprint.sh"
ssh -p "$PORT" -i "$KEY" "$HOST" 'sed -i "s/\r$//" /tmp/pod_sprint.sh; chmod +x /tmp/pod_sprint.sh; nohup /tmp/pod_sprint.sh > /tmp/pod_sprint.out 2>&1 & echo started'
