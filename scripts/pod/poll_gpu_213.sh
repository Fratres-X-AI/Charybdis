#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
for i in $(seq 1 120); do
  echo "GPU_CHECK_${i}"
  bash "$ROOT/watch_gpu_213.sh"
  if ssh -p 40077 -i "${HOME}/.ssh/id_ed25519" root@213.192.2.94 \
    'grep -q "4090 max ladder complete" /tmp/pod_max_gpu.log 2>/dev/null'; then
    echo DONE
    ssh -p 40077 -i "${HOME}/.ssh/id_ed25519" root@213.192.2.94 'tail -n 40 /tmp/pod_max_gpu.log'
    exit 0
  fi
  if ssh -p 40077 -i "${HOME}/.ssh/id_ed25519" root@213.192.2.94 \
    'grep -q "Traceback" /tmp/pod_max_gpu.log 2>/dev/null && ! pgrep -f pod_max_gpu.sh >/dev/null'; then
    echo FAILED
    ssh -p 40077 -i "${HOME}/.ssh/id_ed25519" root@213.192.2.94 'tail -n 50 /tmp/pod_max_gpu.log'
    exit 1
  fi
  sleep 45
done
echo TIMEOUT
