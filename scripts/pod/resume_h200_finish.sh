#!/usr/bin/env bash
# Resume interrupted H200 run on a NEW pod: push pulled checkpoints + babysit to green.
# Usage:
#   EDIT scripts/pod/pod_env.sh with new pod SSH details first
#   RESUME_MODELS=/path/to/artifacts/pod_h200_final_... bash scripts/pod/resume_h200_finish.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

MODELS_SRC="${RESUME_MODELS:-$LOCAL_ROOT/artifacts/pod_h200_final_20260717T143729Z/models}"
if [[ ! -d "$MODELS_SRC" ]]; then
  echo "ERROR: RESUME_MODELS dir missing: $MODELS_SRC"
  exit 1
fi

echo "=== RESUME H200 FINISH pod=${POD_NAME} ==="
echo "models_src=$MODELS_SRC"

echo "=== verify pod + GPU count ==="
ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set -euo pipefail
nvidia-smi -L
ngpu=$(nvidia-smi -L 2>/dev/null | wc -l)
echo "GPU_COUNT=${ngpu}"
if (( ngpu < 1 )); then
  echo "ERROR: no GPUs visible — rent a GPU pod (2× H200 recommended)"
  exit 1
fi
if (( ngpu < 2 )); then
  echo "WARN: only 1 GPU — round-2 will run lanes sequentially (slower)"
fi
REMOTE

echo "=== sync repo ==="
bash "$SCRIPT_DIR/sync_pod.sh"

echo "=== upload resume checkpoints ==="
scp -o StrictHostKeyChecking=no -P "$POD_PORT" -i "$POD_KEY" -r \
  "$MODELS_SRC/"* "$POD_HOST:/workspace/Charybdis/models/"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
source .venv/bin/activate 2>/dev/null || bash scripts/pod/pod_bootstrap_venv.sh && source .venv/bin/activate
export PYTHONPATH=.
python -m pip install -q -c requirements/ci.txt -e ".[dev]" 2>/dev/null || true
if ! python -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
  python -m pip install -q --force-reinstall torch --index-url https://download.pytorch.org/whl/cu126
fi
# Promote best available round-1 checkpoint if lane1 never FINAL'd
if [[ -f models/tcm_so2_lane0_pass05.pt ]]; then
  cp -f models/tcm_so2_lane0_pass05.pt models/tcm_so2.pt
  cp -f models/tcm_so2_lane0_pass05.pt charybdis/models/tcm_so2.pt 2>/dev/null || mkdir -p charybdis/models && cp -f models/tcm_so2_lane0_pass05.pt charybdis/models/tcm_so2.pt
fi
ls -lh models/tcm_so2*.pt | tail -8
REMOTE

echo "=== launch saturate + babysit ==="
bash "$SCRIPT_DIR/kick_saturate_h200.sh"
bash "$SCRIPT_DIR/kick_hotzone_bathy.sh"
exec bash "$SCRIPT_DIR/go_babysit_h200.sh"
