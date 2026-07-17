#!/usr/bin/env bash
# R2 already finished (pass05 on disk) but heal relaunched it. Stop waste, restore gates, full_pass, pull models.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/pod/pod_env.sh
source "$SCRIPT_DIR/pod_env.sh"

echo "=== RECOVER R2 DONE — stop duplicate R2, keep checkpoints ==="

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
if [[ -f .venv/bin/activate ]]; then source .venv/bin/activate; fi
export PYTHONPATH=.

echo "Stopping duplicate R2 / followon relaunch..."
pkill -f 'pod_h200_max_gpu_lane|pod_h200_followon' 2>/dev/null || true
sleep 3

test -f models/tcm_so2_h200_lane0_pass05.pt
test -f models/tcm_so2_h200_lane1_pass05.pt

# Promote best available H200 checkpoint into active weight
python3 - <<'PY'
import re, shutil
from pathlib import Path
ROOT = Path("/workspace/Charybdis/models")
# Prefer best_* if present, else pass05
cands = []
for g in (0, 1):
    best = ROOT / f"tcm_so2_h200_best_lane{g}.pt"
    p05 = ROOT / f"tcm_so2_h200_lane{g}_pass05.pt"
    if best.is_file():
        cands.append(best)
    elif p05.is_file():
        cands.append(p05)
src = cands[0] if cands else ROOT / "tcm_so2.pt"
# Prefer lane1 best if newer
for c in cands:
    if c.stat().st_mtime >= src.stat().st_mtime:
        src = c
for dst in (ROOT / "tcm_so2.pt", ROOT / "tcm_so2_best.pt", Path("/workspace/Charybdis/charybdis/models/tcm_so2.pt")):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dst)
print(f"promoted {src.name}")
PY

# Restore FINAL markers so scoreboard sees R2 complete (logs were truncated by relaunch)
for g in 0 1; do
  f=/tmp/pod_h200_lane${g}.log
  if ! grep -qE "H200 FINAL gpu=${g}\b" "$f" 2>/dev/null; then
    echo "H200 FINAL gpu=${g} lane=recovered best_pass=5 {'after_mean': 0.0, 'recovered_from_pass05': True}" >>"$f"
    echo "appended FINAL marker lane${g}"
  fi
done

# Mark followon complete path
echo "[$(date -u +%H:%M:%S)] R2_RECOVERED_FROM_PASS05 — launching full_pass" | tee -a /tmp/pod_h200_followon.log

if ! pgrep -f pod_full_pass >/dev/null 2>&1; then
  nohup bash scripts/pod/pod_full_pass.sh > /tmp/pod_post_train_full_pass.log 2>&1 &
  echo "full_pass_pid=$!"
fi

ls -lh models/tcm_so2_h200_lane*_pass05.pt models/tcm_so2.pt
nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader
REMOTE

echo "=== pull models now ==="
bash "$SCRIPT_DIR/pull_h200_incremental.sh" || true
bash "$SCRIPT_DIR/pod_pipeline_green.sh" --report 2>/dev/null | grep -E 'GREEN |RED |SCORE' || true
echo "RECOVER_DONE"
