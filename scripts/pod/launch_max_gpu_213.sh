#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
HOST=root@213.192.2.94
PORT=40077
KEY="${HOME}/.ssh/id_ed25519"

bash "$ROOT/sync_pod_213.sh"
LOCAL_ROOT="$(cd "$ROOT/../.." && pwd)"
scp -P "$PORT" -i "$KEY" "${LOCAL_ROOT}/models/tcm_so2.pt" "${HOST}:/workspace/Charybdis/models/tcm_so2.pt"
scp -P "$PORT" -i "$KEY" "$ROOT/pod_max_gpu_213.sh" "${HOST}:/tmp/pod_max_gpu.sh"
ssh -p "$PORT" -i "$KEY" "$HOST" 'mkdir -p /workspace/Charybdis/models; sed -i "s/\r$//" /tmp/pod_max_gpu.sh; chmod +x /tmp/pod_max_gpu.sh; nohup /tmp/pod_max_gpu.sh > /tmp/pod_max_gpu.out 2>&1 & echo max_gpu_started'
