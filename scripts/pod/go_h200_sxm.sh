#!/usr/bin/env bash
# =============================================================================
# 2x H200 SXM — single entrypoint: beginning → 100% GREEN → pull → exit.
#
# Prerequisites (once, on this machine):
#   1. Rent 2x H200 SXM on RunPod (PyTorch CUDA 12.x template, /workspace volume)
#   2. Connect tab → copy "SSH over exposed TCP" (NOT ssh.runpod.io)
#   3. Edit scripts/pod/pod_env.local.sh with POD_NAME / POD_HOST / POD_PORT
#   4. From Git Bash in the repo root:
#        bash scripts/pod/go_h200_sxm.sh
#
# What this does:
#   preflight (2 GPUs) → fast bootstrap → CUDA smoke → sync repo →
#   upload resume checkpoints → launch R1 GPU + CPU elite + hotzone + R2 followon →
#   babysit / heal until pod_pipeline_green → final artifact pull → exit 0
# =============================================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$LOCAL_ROOT"
chmod +x scripts/pod/*.sh 2>/dev/null || true

# shellcheck source=scripts/pod/pod_env.sh
source "$SCRIPT_DIR/pod_env.sh"

export MIN_GPUS="${MIN_GPUS:-2}"
export REQUIRE_H200="${REQUIRE_H200:-0}"
export GPU_MAX_HOURS="${GPU_MAX_HOURS:-12}"
export GPU_POLL_SEC="${GPU_POLL_SEC:-120}"

MODELS_SRC="${RESUME_MODELS:-$LOCAL_ROOT/artifacts/pod_h200_final_20260717T143729Z/models}"
if [[ ! -d "$MODELS_SRC" ]]; then
  MODELS_SRC="$LOCAL_ROOT/models"
fi

echo "============================================================"
echo "  H200 SXM END-TO-END → 100% GREEN"
echo "  pod=${POD_NAME}"
echo "  host=${POD_HOST}:${POD_PORT}"
echo "  resume_models=${MODELS_SRC}"
echo "  max_hours=${GPU_MAX_HOURS}"
echo "============================================================"

bash "$SCRIPT_DIR/pod_preflight.sh"

echo "=== remote fast bootstrap ==="
scp -o StrictHostKeyChecking=no -P "$POD_PORT" -i "$POD_KEY" \
  "$SCRIPT_DIR/pod_fast_bootstrap.sh" \
  "$POD_HOST:/tmp/pod_fast_bootstrap.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
  'mkdir -p /workspace/Charybdis && sed -i "s/\r$//" /tmp/pod_fast_bootstrap.sh && bash /tmp/pod_fast_bootstrap.sh'

bash "$SCRIPT_DIR/ensure_pod_cuda.sh"

echo "=== sync repo ==="
bash "$SCRIPT_DIR/sync_pod.sh"

# Re-push orchestration scripts after sync (authoritative local copies)
tar -C "$LOCAL_ROOT/scripts/pod" --no-same-owner --no-same-permissions -cf - \
  pod_fast_bootstrap.sh \
  pod_quad_gpu_max.sh \
  pod_max_gpu_lane.sh \
  pod_h200_max_gpu_lane.sh \
  pod_h200_followon.sh \
  pod_cpu_elite_parallel.sh \
  pod_hotzone_bathy.sh \
  pod_full_pass.sh \
  pod_heal_h200.sh \
  2>/dev/null | ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
  "mkdir -p /workspace/Charybdis/scripts/pod && tar --no-same-owner -xf - -C /workspace/Charybdis/scripts/pod && chmod +x /workspace/Charybdis/scripts/pod/*.sh"

if [[ -d "$MODELS_SRC" ]]; then
  echo "=== upload resume checkpoints ==="
  scp -o StrictHostKeyChecking=no -P "$POD_PORT" -i "$POD_KEY" -r \
    "$MODELS_SRC/"* "$POD_HOST:/workspace/Charybdis/models/"
fi

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
for f in scripts/pod/*.sh; do sed -i 's/\r$//' "$f"; chmod +x "$f"; done
export PYTHONPATH=.
# Prefer venv if present
if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# Promote best available round-1 checkpoint into the active weight
if [[ -f models/tcm_so2_lane0_pass05.pt ]]; then
  cp -f models/tcm_so2_lane0_pass05.pt models/tcm_so2.pt
  mkdir -p charybdis/models
  cp -f models/tcm_so2_lane0_pass05.pt charybdis/models/tcm_so2.pt
elif [[ -f models/tcm_so2_best_lane0.pt ]]; then
  cp -f models/tcm_so2_best_lane0.pt models/tcm_so2.pt
  mkdir -p charybdis/models
  cp -f models/tcm_so2_best_lane0.pt charybdis/models/tcm_so2.pt
fi
ls -lh models/tcm_so2*.pt 2>/dev/null | tail -12 || true

# Kill stale workers from a previous aborted run
pkill -f 'pod_max_gpu_lane|pod_quad_gpu_max|pod_h200_followon|pod_h200_max_gpu_lane|pod_cpu_elite|pod_hotzone_bathy|pod_full_pass' 2>/dev/null || true
sleep 2

echo "[launch] GPU round-1 (2 lanes)"
nohup bash scripts/pod/pod_quad_gpu_max.sh > /tmp/pod_quad_gpu.out 2>&1 &

echo "[launch] H200 round-2 followon (waits for round-1)"
nohup bash scripts/pod/pod_h200_followon.sh > /tmp/pod_h200_followon_stdout.log 2>&1 &

echo "[launch] CPU elite parallel"
nohup bash scripts/pod/pod_cpu_elite_parallel.sh > /tmp/pod_cpu_elite_stdout.log 2>&1 &

echo "[launch] hotzone GEBCO"
nohup bash scripts/pod/pod_hotzone_bathy.sh > /tmp/pod_hotzone_bathy_stdout.log 2>&1 &

sleep 8
echo "=== LAUNCH STATUS ==="
nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used --format=csv,noheader || true
pgrep -af 'pod_max_gpu_lane|pod_quad_gpu|pod_h200_followon|hybrid_validate|pod_hotzone' | head -20 || true
REMOTE

echo "=== babysit until 100% GREEN ==="
exec bash "$SCRIPT_DIR/babysit_h200_elite.sh"
