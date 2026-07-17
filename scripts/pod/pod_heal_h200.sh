#!/usr/bin/env bash
# Relaunch any dead H200 pipeline workers (best-effort heal).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

echo "=== HEAL H200 pod=${POD_NAME} ==="

bash "$SCRIPT_DIR/ensure_pod_cuda.sh" || true
bash "$SCRIPT_DIR/kick_saturate_h200.sh"

tar -C "$LOCAL_ROOT" --no-same-owner --no-same-permissions -cf - \
  validation/hotzone_gebco_regions.json \
  scripts/prepare_gebco_tile.py \
  scripts/pod/pod_hotzone_bathy.sh \
  scripts/pod/pod_h200_followon.sh \
  scripts/pod/pod_full_pass.sh \
  2>/dev/null | ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
  "tar --no-same-owner -xf - -C /workspace/Charybdis && chmod +x /workspace/Charybdis/scripts/pod/*.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
for f in scripts/pod/*.sh; do sed -i 's/\r$//' "$f"; chmod +x "$f"; done
source .venv/bin/activate 2>/dev/null || true

r1_done=0
for g in 0 1; do
  grep -qE "FINAL gpu=${g}\b" /tmp/pod_gpu_lane${g}.log 2>/dev/null && r1_done=$((r1_done+1)) || true
done

if (( r1_done < 2 )); then
  if ! pgrep -f 'pod_max_gpu_lane.sh|pod_quad_gpu_max.sh' >/dev/null 2>&1; then
    echo "[heal] round-1 GPU lanes dead with r1_done=${r1_done}/2 — relaunch quad"
    nohup bash scripts/pod/pod_quad_gpu_max.sh > /tmp/pod_quad_gpu.out 2>&1 &
  fi
fi

if (( r1_done >= 2 )) && ! pgrep -f pod_h200_followon >/dev/null 2>&1; then
  r2_done=0
  for g in 0 1; do
    grep -qE "H200 FINAL gpu=${g}\b" /tmp/pod_h200_lane${g}.log 2>/dev/null && r2_done=$((r2_done+1)) || true
  done
  if (( r2_done < 2 )); then
    echo "[heal] round-1 done, followon dead — relaunch followon"
    nohup bash scripts/pod/pod_h200_followon.sh > /tmp/pod_h200_followon_stdout.log 2>&1 &
  fi
fi

if ! pgrep -f pod_cpu_elite_parallel >/dev/null 2>&1; then
  # Prefer any completed green cpu_elite tree — do not thrash re-runs inside a 2h window.
  cpu_green=0
  if python3 - <<'PY'
import json
from pathlib import Path
jobs = ["mission_engineering","holdout_harbor","holdout_deep","harbor_release","deep_release"]
for root in sorted(Path("artifacts/validation").glob("*/cpu_elite")):
    ok = True
    for job in jobs:
        p = root / job / "matrix_summary.json"
        if not p.is_file() or not json.loads(p.read_text()).get("passed"):
            ok = False
            break
    if ok:
        raise SystemExit(0)
raise SystemExit(1)
PY
  then
    cpu_green=1
    echo "[heal] cpu elite already green — leave alone"
  fi
  if (( cpu_green == 0 )); then
    if [[ ! -f /tmp/pod_cpu_elite.log ]] || ! grep -q CPU_ELITE_COMPLETE /tmp/pod_cpu_elite.log 2>/dev/null; then
      echo "[heal] cpu elite incomplete — relaunch"
      nohup bash scripts/pod/pod_cpu_elite_parallel.sh > /tmp/pod_cpu_elite_stdout.log 2>&1 &
    fi
  fi
fi

if ! pgrep -f pod_hotzone_bathy >/dev/null 2>&1; then
  needs_hz=1
  hz_root=$(ls -1d artifacts/validation/*/hotzone_bathymetry 2>/dev/null | tail -1 || true)
  if [[ -n "$hz_root" ]]; then
    if python3 - <<PY
import json
from pathlib import Path
regions = json.loads(Path("validation/hotzone_gebco_regions.json").read_text())
root = Path("${hz_root}")
ok = True
for r in regions:
    st = (root / r["id"] / "status.txt").read_text().strip() if (root / r["id"] / "status.txt").is_file() else "missing"
    if st != "OK":
        ok = False
        break
raise SystemExit(0 if ok else 1)
PY
    then
      needs_hz=0
    fi
  fi
  if (( needs_hz )); then
    echo "[heal] hotzone incomplete — relaunch"
    nohup bash scripts/pod/pod_hotzone_bathy.sh > /tmp/pod_hotzone_bathy_stdout.log 2>&1 &
  fi
fi

echo "HEAL_STATUS r1_done=${r1_done}/2 gpu_procs=$(pgrep -c -f pod_max_gpu_lane || echo 0) followon=$(pgrep -c -f pod_h200_followon || echo 0) validate=$(pgrep -c -f hybrid_validate || echo 0)"
REMOTE

bash "$SCRIPT_DIR/kick_hotzone_bathy.sh" || true
echo "HEAL_H200_DONE"
