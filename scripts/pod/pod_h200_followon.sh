#!/usr/bin/env bash
# Wait for round-1 GPU lanes, promote, launch H200-max round 2, then re-validate.
set -euo pipefail

REPO=/workspace/Charybdis
LOG=/tmp/pod_h200_followon.log
: >"$LOG"

ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

cd "$REPO"
if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
export PYTHONPATH=.
PY=python3
command -v python >/dev/null 2>&1 && PY=python

log "H200_FOLLOWON waiting for round-1 lanes..."
while pgrep -f 'pod_max_gpu_lane.sh' >/dev/null 2>&1; do
  sleep 45
done
while pgrep -f 'pod_quad_gpu_max.sh' >/dev/null 2>&1; do
  sleep 15
done
log "round-1 finished — promoting best lane"

"$PY" - <<'PY' | tee -a "$LOG"
import re
import shutil
from pathlib import Path

ROOT = Path("/workspace/Charybdis/models")
best_mean = 1e9
best_path = ROOT / "tcm_so2.pt"
for lane_log in sorted(Path("/tmp").glob("pod_gpu_lane*.log")):
    text = lane_log.read_text(encoding="utf-8", errors="ignore")
    finals = re.findall(
        r"FINAL gpu=(\d) lane=\w+ best_pass=(\d+) \{[^}]*'after_mean': ([0-9.]+)",
        text,
    )
    if not finals:
        continue
    gpu, _, mean = finals[-1]
    mean_f = float(mean)
    candidate = ROOT / f"tcm_so2_best_lane{gpu}.pt"
    if mean_f < best_mean and candidate.exists():
        best_mean = mean_f
        best_path = candidate
        print(f"promote round1 gpu={gpu} after_mean={mean_f:.1f}m", flush=True)

for dst in (
    ROOT / "tcm_so2.pt",
    ROOT / "tcm_so2_best.pt",
    Path("/workspace/Charybdis/charybdis/models/tcm_so2.pt"),
):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(best_path, dst)
print(f"round1 saved {best_path.name} -> tcm_so2.pt", flush=True)
PY

log "H200 round-2 launch (8192 batch, tail-weighted eval)"
pkill -f pod_h200_max_gpu_lane || true
sleep 2
nohup bash scripts/pod/pod_h200_max_gpu_lane.sh 0 e > /tmp/pod_h200_lane0.log 2>&1 &
nohup bash scripts/pod/pod_h200_max_gpu_lane.sh 1 f > /tmp/pod_h200_lane1.log 2>&1 &
sleep 10
log "round-2 lanes=$(pgrep -c -f pod_h200_max_gpu_lane || echo 0)"
nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader 2>/dev/null | tee -a "$LOG" || true

log "waiting for round-2 lanes..."
while pgrep -f 'pod_h200_max_gpu_lane.sh' >/dev/null 2>&1; do
  sleep 60
done

log "round-2 finished — promoting best H200 lane"
"$PY" - <<'PY' | tee -a "$LOG"
import re
import shutil
from pathlib import Path

ROOT = Path("/workspace/Charybdis/models")
best_mean = 1e9
best_path = ROOT / "tcm_so2.pt"
for lane_log in sorted(Path("/tmp").glob("pod_h200_lane*.log")):
    text = lane_log.read_text(encoding="utf-8", errors="ignore")
    finals = re.findall(
        r"H200 FINAL gpu=(\d) lane=\w+ best_pass=(\d+) \{[^}]*'after_mean': ([0-9.]+)",
        text,
    )
    if not finals:
        continue
    gpu, _, mean = finals[-1]
    mean_f = float(mean)
    candidate = ROOT / f"tcm_so2_h200_best_lane{gpu}.pt"
    if mean_f < best_mean and candidate.exists():
        best_mean = mean_f
        best_path = candidate
        print(f"promote round2 gpu={gpu} after_mean={mean_f:.1f}m", flush=True)

for dst in (
    ROOT / "tcm_so2.pt",
    ROOT / "tcm_so2_best.pt",
    Path("/workspace/Charybdis/charybdis/models/tcm_so2.pt"),
):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(best_path, dst)
print(f"round2 saved {best_path.name} -> tcm_so2.pt", flush=True)
PY

log "post-train validation burst with promoted model"
nohup bash scripts/pod/pod_full_pass.sh > /tmp/pod_post_train_full_pass.log 2>&1 &
log "H200_FOLLOWON_COMPLETE queued full_pass"
