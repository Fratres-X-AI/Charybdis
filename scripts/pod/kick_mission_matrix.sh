#!/usr/bin/env bash
# Non-blocking mission matrix on pod (parallel with other lanes).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

echo "[kick_mission] sync -> ${POD_NAME}"
bash "$LOCAL_ROOT/scripts/pod/sync_pod.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
for f in scripts/pod/*.sh; do sed -i 's/\r$//' "$f"; chmod +x "$f"; done

pkill -f 'hybrid_validate_mission_matrix' 2>/dev/null || true

nohup bash -c '
  set -euo pipefail
  cd /workspace/Charybdis
  echo "[kick_mission] start $(date -u +%H:%M:%SZ)" >> /tmp/pod_mission_matrix.log
  bash scripts/pod/pod_bootstrap_venv.sh >> /tmp/pod_mission_matrix.log 2>&1
  source .venv/bin/activate
  export PYTHONPATH=. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 MPLBACKEND=Agg
  python scripts/hybrid_validate_mission_matrix.py \
    --tier engineering \
    --runs 64 \
    --workers 31 \
    --allow-dirty >> /tmp/pod_mission_matrix.log 2>&1
  echo "[kick_mission] done $(date -u +%H:%M:%SZ)" >> /tmp/pod_mission_matrix.log
' > /dev/null 2>&1 &

sleep 1
echo "kicked_mission pid=$!"
tail -3 /tmp/pod_mission_matrix.log 2>/dev/null || echo "(log starting)"
pgrep -af 'hybrid_validate_mission|pod_mission' || echo "procs pending"
REMOTE

echo "[kick_mission] detached — tail: ssh pod tail -f /tmp/pod_mission_matrix.log"
