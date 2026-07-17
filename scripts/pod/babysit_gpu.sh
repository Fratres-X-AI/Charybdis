#!/usr/bin/env bash
# Babysit visible GPU lanes until all FINAL or lane complete. Poll 90s. Git Bash only.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
PULL_DEST="$LOCAL_ROOT/artifacts/pod_gpu_final_${STAMP}"
INTERVAL="${GPU_POLL_SEC:-90}"
MAX_HOURS="${GPU_MAX_HOURS:-3}"
MAX_LOOPS=$((MAX_HOURS * 3600 / INTERVAL))

REMOTE_GPU_COUNT="$(ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" 'nvidia-smi -L 2>/dev/null | wc -l' 2>/dev/null || true)"
GPU_TARGET="${GPU_TARGET:-$REMOTE_GPU_COUNT}"
if ! [[ "$GPU_TARGET" =~ ^[0-9]+$ ]] || (( GPU_TARGET < 1 )); then
  GPU_TARGET=4
fi
if (( GPU_TARGET > 4 )); then
  GPU_TARGET=4
fi

echo "=== BABYSIT GPU pod=${POD_NAME} lanes=${GPU_TARGET} interval=${INTERVAL}s ==="

all_done() {
  ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" "
    target=${GPU_TARGET}
    done=0
    for ((g=0; g<target; g++)); do
      if grep -qE "FINAL gpu=\${g}|lane complete" /tmp/pod_gpu_lane\${g}.log 2>/dev/null; then
        done=\$((done+1))
      fi
    done
    echo \$done
  "
}

loop=0
while (( loop < MAX_LOOPS )); do
  loop=$((loop + 1))
  echo ""
  echo "========== gpu loop $loop $(date -u +%H:%M:%SZ) =========="
  bash "$SCRIPT_DIR/gpu_status.sh" || true

  finished=$(all_done || echo 0)
  echo "gpu_lanes_finished=${finished}/${GPU_TARGET}"

  if [[ "${finished}" == "${GPU_TARGET}" ]]; then
    echo "=== ALL GPU LANES DONE - promote + pull ==="
    ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE' || true
cd /workspace/Charybdis
if [[ -f scripts/pod/pod_quad_gpu_max.sh ]]; then
  # promotion logic only (lanes already finished)
  python3 - <<'PY'
import re, shutil
from pathlib import Path
ROOT = Path("/workspace/Charybdis/models")
best_mean, best_path = 1e9, ROOT / "tcm_so2.pt"
for lane_log in sorted(Path("/tmp").glob("pod_gpu_lane*.log")):
    text = lane_log.read_text(encoding="utf-8", errors="ignore")
    finals = re.findall(r"FINAL gpu=(\d) lane=\w+ best_pass=(\d+) \{[^}]*'after_mean': ([0-9.]+)", text)
    if not finals:
        continue
    gpu, _, mean = finals[-1]
    mean_f = float(mean)
    cand = ROOT / f"tcm_so2_best_lane{gpu}.pt"
    if mean_f < best_mean and cand.exists():
        best_mean, best_path = mean_f, cand
        print(f"promote gpu={gpu} after_mean={mean_f:.1f}m")
if best_path.exists():
    for dst in (
        ROOT / "tcm_so2.pt",
        ROOT / "tcm_so2_best.pt",
        Path("/workspace/Charybdis/charybdis/models/tcm_so2.pt"),
    ):
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(best_path, dst)
    print(f"saved {best_path.name} -> tcm_so2.pt")
PY
fi
REMOTE
    mkdir -p "$PULL_DEST/models" "$PULL_DEST/logs"
    scp -o StrictHostKeyChecking=no -P "$POD_PORT" -i "$POD_KEY" -r \
      "$POD_HOST:/workspace/Charybdis/models/" "$PULL_DEST/" 2>/dev/null || true
    for ((g=0; g<GPU_TARGET; g++)); do
      scp -o StrictHostKeyChecking=no -P "$POD_PORT" -i "$POD_KEY" \
        "$POD_HOST:/tmp/pod_gpu_lane${g}.log" "$PULL_DEST/logs/" 2>/dev/null || true
    done
    for f in pod_quad_gpu.log pod_quad_gpu.out; do
      scp -o StrictHostKeyChecking=no -P "$POD_PORT" -i "$POD_KEY" \
        "$POD_HOST:/tmp/$f" "$PULL_DEST/logs/" 2>/dev/null || true
    done
    echo "GPU_BABYSIT_DONE dest=$PULL_DEST"
    du -sh "$PULL_DEST" 2>/dev/null || true
    exit 0
  fi

  sleep "$INTERVAL"
done

echo "GPU_BABYSIT_TIMEOUT — pulling best available"
bash "$SCRIPT_DIR/pull_quad_final.sh" || true
exit 1
