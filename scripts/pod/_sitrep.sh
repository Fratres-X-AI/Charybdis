#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
# shellcheck source=scripts/pod/pod_env.sh
source scripts/pod/pod_env.sh

echo "=== SITREP $(date -u +%H:%M:%SZ) ==="
ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set +e
cd /workspace/Charybdis
nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader
echo "procs: lanes=$(pgrep -c -f 'pod_max_gpu_lane.sh'||echo 0) r2=$(pgrep -c -f 'pod_h200_max_gpu_lane'||echo 0) followon=$(pgrep -c -f pod_h200_followon||echo 0) cpu=$(pgrep -c -f hybrid_validate||echo 0) hotzone=$(pgrep -c -f pod_hotzone_bathy||echo 0)"
for g in 0 1; do
  f=/tmp/pod_gpu_lane${g}.log
  echo "--- gpu${g} ---"
  if grep -qE "FINAL gpu=${g}\b" "$f" 2>/dev/null; then
    grep -E "FINAL gpu=${g}\b" "$f" | tail -1
  else
    grep -E 'PASS |epoch |new_best|FINAL' "$f" 2>/dev/null | tail -3
  fi
done
echo "--- cpu elite ---"
ls -1 artifacts/validation/*/cpu_elite/*/matrix_summary.json 2>/dev/null | tail -8
for m in artifacts/validation/*/cpu_elite/*/matrix_summary.json; do
  [[ -f "$m" ]] || continue
  python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(sys.argv[1].split('/')[-2], 'pass='+str(d.get('passed')))" "$m" 2>/dev/null
done | tail -8
echo "--- hotzone ---"
ls artifacts/validation/*/hotzone_bathymetry/*/status.txt 2>/dev/null | while read -r s; do
  echo "$(basename "$(dirname "$s")")=$(cat "$s")"
done | tail -12
echo "--- r2 ---"
grep -E 'H200 FINAL|PASS |epoch ' /tmp/pod_h200_lane0.log 2>/dev/null | tail -2
grep -E 'H200 FINAL|PASS |epoch ' /tmp/pod_h200_lane1.log 2>/dev/null | tail -2
REMOTE

echo ""
echo "=== green scoreboard ==="
bash scripts/pod/pod_pipeline_green.sh --report 2>/dev/null | grep -E 'GREEN|RED|SCORE|PIPELINE' || true

echo ""
echo "=== local babysit ==="
tail -5 artifacts/go_h200_sxm.log 2>/dev/null | sed 's/\r//' || true
age=$(( $(date +%s) - $(stat -c %Y artifacts/go_h200_sxm.log 2>/dev/null || stat -f %m artifacts/go_h200_sxm.log) ))
echo "log_age_s=$age"
if (( age > 300 )); then
  echo "WARN babysit log stale — restarting babysit"
  nohup bash scripts/pod/babysit_h200_elite.sh >>artifacts/go_h200_sxm.log 2>&1 &
  echo "restarted pid=$!"
fi
