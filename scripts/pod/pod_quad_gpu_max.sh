#!/usr/bin/env bash
# Max up to 4 visible GPUs in parallel, then promote the best lane to tcm_so2.pt.
set -euo pipefail
REPO=/workspace/Charybdis
LOG=/tmp/pod_quad_gpu.log
: >"$LOG"

ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

cd "$REPO"
mkdir -p models
if [[ ! -f models/tcm_so2.pt ]]; then
  if [[ -f charybdis/models/tcm_so2.pt ]]; then
    cp -f charybdis/models/tcm_so2.pt models/tcm_so2.pt
  else
    log "ERROR missing models/tcm_so2.pt"
    exit 1
  fi
fi

NGPU=$(nvidia-smi -L 2>/dev/null | wc -l)
if (( NGPU > 4 )); then
  NGPU=4
fi
log "GPU max start gpus=${NGPU}"

PIDS=()
for gpu in 0 1 2 3; do
  if (( gpu >= NGPU )); then
    log "skip gpu${gpu} (only ${NGPU} visible)"
    continue
  fi
  case "$gpu" in
    0) lane=a ;;
    1) lane=b ;;
    2) lane=c ;;
    3) lane=d ;;
  esac
  bash scripts/pod/pod_max_gpu_lane.sh "$gpu" "$lane" 2>&1 | tee -a "/tmp/pod_gpu_lane${gpu}.log" &
  PIDS+=($!)
  log "started gpu${gpu} lane=${lane} pid=${PIDS[-1]}"
done

if ((${#PIDS[@]} == 0)); then
  log "QUAD_GPU_SKIP no cuda devices"
  exit 0
fi

wait "${PIDS[@]}"
log "all GPU lanes finished"

python - <<'PY' | tee -a "$LOG"
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
    gpu, _pass, mean = finals[-1]
    mean_f = float(mean)
    candidate = ROOT / f"tcm_so2_best_lane{gpu}.pt"
    if mean_f < best_mean and candidate.exists():
        best_mean = mean_f
        best_path = candidate
        print(f"promote lane gpu={gpu} after_mean={mean_f:.1f}m", flush=True)

for dst in (
    ROOT / "tcm_so2.pt",
    ROOT / "tcm_so2_best.pt",
    Path("/workspace/Charybdis/charybdis/models/tcm_so2.pt"),
):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(best_path, dst)
print(f"saved models/tcm_so2.pt from {best_path.name}", flush=True)
PY

log "GPU_MAX_COMPLETE"
