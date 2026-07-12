#!/usr/bin/env bash
# Max both 4090s in parallel, promote best lane to tcm_so2.pt.
set -euo pipefail
REPO=/workspace/Charybdis
LOG=/tmp/pod_dual_gpu.log
: >"$LOG"

ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

cd "$REPO"
mkdir -p models
if [[ ! -f models/tcm_so2.pt ]]; then
  log "ERROR missing models/tcm_so2.pt"
  exit 1
fi

log "start dual GPU max training"
bash scripts/pod/pod_max_gpu_lane.sh 0 a 2>&1 | tee -a /tmp/pod_gpu_lane0.log &
PID0=$!
bash scripts/pod/pod_max_gpu_lane.sh 1 b 2>&1 | tee -a /tmp/pod_gpu_lane1.log &
PID1=$!
wait "$PID0" "$PID1"
log "both lanes finished"

python - <<'PY' | tee -a "$LOG"
import re
from pathlib import Path

ROOT = Path("/workspace/Charybdis/models")
best_mean = 1e9
best_path = ROOT / "tcm_so2.pt"
for lane_log in [Path("/tmp/pod_gpu_lane0.log"), Path("/tmp/pod_gpu_lane1.log")]:
    text = lane_log.read_text(encoding="utf-8", errors="ignore")
    finals = re.findall(r"FINAL gpu=(\d) lane=\w+ best_pass=(\d+) \{[^}]*'after_mean': ([0-9.]+)", text)
    if not finals:
        continue
    gpu, _pass, mean = finals[-1]
    mean_f = float(mean)
    candidate = ROOT / f"tcm_so2_best_lane{gpu}.pt"
    if mean_f < best_mean and candidate.exists():
        best_mean = mean_f
        best_path = candidate
        print(f"promote lane gpu={gpu} after_mean={mean_f:.1f}m", flush=True)

import shutil
shutil.copy(best_path, ROOT / "tcm_so2.pt")
shutil.copy(best_path, ROOT / "tcm_so2_best.pt")
print(f"saved models/tcm_so2.pt from {best_path.name}", flush=True)
PY

log "dual GPU max complete"
