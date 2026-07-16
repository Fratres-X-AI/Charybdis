#!/usr/bin/env bash
# Unblock sequential tails on live pod + fix Blackwell GPU torch. Does NOT kill CPU validation.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

bash "$LOCAL_ROOT/scripts/pod/sync_pod.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
for f in scripts/pod/*.sh; do sed -i 's/\r$//' "$f"; chmod +x "$f"; done
source .venv/bin/activate
export PYTHONPATH=. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 MPLBACKEND=Agg

OUT=$(ls -1dt artifacts/validation/*/elite_phase34 2>/dev/null | head -1 || true)
if [[ -z "$OUT" ]]; then
  STAMP="$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD 2>/dev/null || echo synced)"
  OUT="artifacts/validation/${STAMP}/elite_phase34"
  mkdir -p "$OUT"
fi
echo "parallel_out=$OUT"

launch_if_missing() {
  local pattern="$1"
  local name="$2"
  shift 2
  if pgrep -f "$pattern" >/dev/null 2>&1; then
    echo "skip $name (already running)"
    return 0
  fi
  echo "START PARALLEL $name"
  nohup "$@" >"/tmp/pod_unblock_${name}.log" 2>&1 &
}

# --- Unblock jobs that were chained sequentially ---
launch_if_missing "deep_release.*elite_phase34/deep_release" deep_rel \
  python scripts/hybrid_validate_deep_matrix.py \
  --tier release --runs 256 --workers 28 --allow-dirty \
  --output-dir "${OUT}/deep_release"

launch_if_missing "deep_worst_release.*elite_phase34/deep_worst_release" deep_worst_rel \
  python scripts/hybrid_validate_deep_matrix.py \
  --tier release --runs 512 --workers 28 --allow-dirty \
  --scenarios deep_midwater deep_long_blackout deep_sparse_bathymetry \
  --output-dir "${OUT}/deep_worst_release"

launch_if_missing "release_grade.*harbor_release" rel_grade_h \
  python scripts/hybrid_validate_matrix.py \
  --tier release --runs 256 --workers 28 --allow-dirty \
  --output-dir "${OUT}/release_grade_harbor"

launch_if_missing "release_grade.*deep_release" rel_grade_d \
  python scripts/hybrid_validate_deep_matrix.py \
  --tier release --runs 256 --workers 28 --allow-dirty \
  --output-dir "${OUT}/release_grade_deep"

# --- Fix Blackwell GPU: cu130 torch ---
echo "fixing torch for sm_120 Blackwell..."
python -m pip install -q --force-reinstall torch --index-url https://download.pytorch.org/whl/cu130
python - <<'PY'
import torch
print("torch", torch.__version__, "cuda", torch.cuda.is_available(), "count", torch.cuda.device_count())
if torch.cuda.is_available():
    print("gpu0", torch.cuda.get_device_name(0))
    x = torch.randn(4096, 4096, device="cuda")
    y = x @ x
    print("matmul_ok", float(y[0,0]))
PY

pkill -f pod_max_gpu_lane || true
sleep 2
for gpu in 0 1 2 3; do
  case "$gpu" in 0) lane=a ;; 1) lane=b ;; 2) lane=c ;; 3) lane=d ;; esac
  if ! pgrep -f "pod_max_gpu_lane.sh ${gpu}" >/dev/null 2>&1; then
    echo "GPU PARALLEL gpu=${gpu} lane=${lane}"
    nohup bash scripts/pod/pod_max_gpu_lane.sh "$gpu" "$lane" >"/tmp/pod_gpu_lane${gpu}.log" 2>&1 &
  fi
done

sleep 3
echo "=== PARALLEL STATUS ==="
echo "validate_procs=$(pgrep -c -f hybrid_validate 2>/dev/null || echo 0)"
echo "gpu_lanes=$(pgrep -c -f pod_max_gpu_lane 2>/dev/null || echo 0)"
pgrep -af 'hybrid_validate|pod_max_gpu_lane' | head -20 || true
nvidia-smi --query-gpu=index,utilization.gpu,memory.used,power.draw --format=csv,noheader 2>/dev/null || true
REMOTE

echo "UNBLOCK_PARALLEL_DONE"
