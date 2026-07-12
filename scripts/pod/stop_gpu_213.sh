#!/usr/bin/env bash
set -euo pipefail
HOST=root@213.192.2.94
PORT=40077
KEY="${HOME}/.ssh/id_ed25519"
ssh -p "$PORT" -i "$KEY" "$HOST" <<'REMOTE'
set -euo pipefail
echo "stopping gpu ladder after pass 4"
pkill -f pod_max_gpu.sh || true
sleep 2
pgrep -af pod_max_gpu || echo "gpu_ladder_stopped"
cd /workspace/Charybdis
if [[ -f models/tcm_so2_pass04.pt ]]; then
  cp -f models/tcm_so2_pass04.pt models/tcm_so2.pt
  cp -f models/tcm_so2_pass04.pt models/tcm_so2_best.pt
  echo "promoted pass04 checkpoint"
elif [[ -f models/tcm_so2_pass03.pt ]]; then
  cp -f models/tcm_so2_pass03.pt models/tcm_so2.pt
  cp -f models/tcm_so2_pass03.pt models/tcm_so2_best.pt
  echo "promoted pass03 checkpoint"
fi
ls -la models/tcm_so2*.pt 2>/dev/null || true
echo "stopped_ok"
REMOTE
