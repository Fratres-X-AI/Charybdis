#!/usr/bin/env bash
set -euo pipefail
HOST="root@64.247.206.218"
PORT="14049"
KEY="${HOME}/.ssh/id_ed25519"
ssh -p "$PORT" -i "$KEY" -o BatchMode=yes -T "$HOST" 'wc -l /workspace/Charybdis/logs/pod/phase1.log; tail -n 500 /workspace/Charybdis/logs/pod/phase1.log'
