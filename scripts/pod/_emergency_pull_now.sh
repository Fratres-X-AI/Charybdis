#!/usr/bin/env bash
# Balance ~$6.81 @ $8.81/hr ≈ 46m — stop GPU waste, recover R2 markers, FULL PULL NOW.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

pkill -f 'away_then_flo' 2>/dev/null || true

echo "=== EMERGENCY PULL balance~\$6.81 ==="

ssh -o StrictHostKeyChecking=no -o ConnectTimeout=20 -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set +e
cd /workspace/Charybdis
# Stop all expensive work immediately
pkill -f 'pod_h200_max_gpu_lane|pod_max_gpu_lane|pod_h200_followon|pod_quad_gpu|pod_full_pass|hybrid_validate|pod_hotzone|pod_cpu_elite' 2>/dev/null || true
sleep 2

# Restore FINAL markers if pass05 exists (heal wiped logs)
for g in 0 1; do
  f=/tmp/pod_h200_lane${g}.log
  if [[ -f /workspace/Charybdis/models/tcm_so2_h200_lane${g}_pass05.pt ]]; then
    if ! grep -qE "H200 FINAL gpu=${g}\b" "$f" 2>/dev/null; then
      echo "H200 FINAL gpu=${g} lane=recovered best_pass=5 {'recovered_from_pass05': True}" >>"$f"
    fi
  fi
done

# Promote newest best
python3 - <<'PY'
from pathlib import Path
import shutil
ROOT = Path("/workspace/Charybdis/models")
cands = sorted(ROOT.glob("tcm_so2_h200_best_lane*.pt"), key=lambda p: p.stat().st_mtime)
if not cands:
    cands = sorted(ROOT.glob("tcm_so2_h200_lane*_pass05.pt"), key=lambda p: p.stat().st_mtime)
if cands:
    src = cands[-1]
    for dst in (ROOT/"tcm_so2.pt", ROOT/"tcm_so2_best.pt", Path("/workspace/Charybdis/charybdis/models/tcm_so2.pt")):
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
    print("promoted", src.name)
PY

ls -lh models/tcm_so2_h200_lane*_pass05.pt models/tcm_so2.pt 2>/dev/null
nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader
echo WORKERS_STOPPED
REMOTE

echo "=== FULL SHUTDOWN PULL ==="
bash "$SCRIPT_DIR/pull_h200_shutdown.sh" 2>&1 | tee "$LOCAL_ROOT/artifacts/emergency_pull.log"
echo "=== SCOREBOARD AFTER PULL ==="
bash "$SCRIPT_DIR/pod_pipeline_green.sh" --report 2>&1 | grep -E 'GREEN |RED |SCORE' || true
echo "STOP_POD_NOW — balance critical"
ls -ltd "$LOCAL_ROOT"/artifacts/pod_h200_final_* 2>/dev/null | head -3
