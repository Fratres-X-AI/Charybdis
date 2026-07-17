#!/usr/bin/env bash
# Live status reporter — one block every INTERVAL seconds for DURATION seconds.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

INTERVAL="${REPORT_INTERVAL_SEC:-90}"
DURATION="${REPORT_DURATION_SEC:-3600}"
END=$((SECONDS + DURATION))
N=0

while (( SECONDS < END )); do
  N=$((N + 1))
  echo ""
  echo "========== H200 STATUS REPORT #${N} $(date -u +%Y-%m-%dT%H:%M:%SZ) =========="
  echo "pod=${POD_NAME} host=${POD_HOST}:${POD_PORT}"

  if ! ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set +e
cd /workspace/Charybdis 2>/dev/null || { echo "repo_missing"; exit 0; }

echo "--- GPU ---"
nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total --format=csv,noheader 2>/dev/null || echo "no nvidia-smi"

echo "--- ROUND 1 LANES ---"
for g in 0 1; do
  echo -n "gpu${g}: "
  if [[ -f /tmp/pod_gpu_lane${g}.log ]]; then
    grep -E 'PASS |after_mean|new_best|FINAL|lane complete' /tmp/pod_gpu_lane${g}.log 2>/dev/null | tail -3 || tail -2 /tmp/pod_gpu_lane${g}.log
  else
    echo "no log"
  fi
done

echo "--- ROUND 2 H200 LANES ---"
for g in 0 1; do
  echo -n "h200_gpu${g}: "
  if [[ -f /tmp/pod_h200_lane${g}.log ]]; then
    grep -E 'H200 PASS|after_mean|new_best|H200 FINAL|h200 lane complete' /tmp/pod_h200_lane${g}.log 2>/dev/null | tail -3 || echo "waiting"
  else
    echo "not started"
  fi
done

echo "--- ORCHESTRATORS ---"
pgrep -af 'pod_quad_gpu_max|pod_h200_followon|pod_cpu_elite|pod_full_pass|pod_max_gpu_lane|pod_h200_max_gpu_lane' 2>/dev/null | head -8 || echo "none"

echo "--- CPU VALIDATION ---"
echo "hybrid_validate_procs=$(pgrep -c -f hybrid_validate 2>/dev/null || echo 0)"
echo "load=$(cat /proc/loadavg 2>/dev/null || echo n/a)"
echo "mem=$(free -h 2>/dev/null | awk '/Mem:/ {print $3 "/" $2}' || echo n/a)"

echo "--- CPU ELITE JOBS ---"
for j in mission holdout_h holdout_d harbor_rel deep_rel; do
  log="/tmp/pod_cpu_${j}.log"
  if [[ -f "$log" ]]; then
    tail -1 "$log" 2>/dev/null | sed "s/^/${j}: /" || true
  fi
done
if [[ -f /tmp/pod_highres_bathy.log ]]; then
  echo -n "highres: "
  grep -E 'PASS|FAIL|complete|CEP|engineering|release' /tmp/pod_highres_bathy.log 2>/dev/null | tail -2 || tail -1 /tmp/pod_highres_bathy.log
fi
if [[ -f /tmp/pod_hotzone_bathy.log ]]; then
  echo -n "hotzone: "
  grep -E 'region |HOTZONE|pass=' /tmp/pod_hotzone_bathy.log 2>/dev/null | tail -4 || tail -2 /tmp/pod_hotzone_bathy.log
fi

echo "--- MODEL CHECKPOINTS ---"
ls -lh models/tcm_so2*.pt 2>/dev/null | tail -6 || echo "no checkpoints"

echo "--- FOLLOWON ---"
if [[ -f /tmp/pod_h200_followon.log ]]; then
  tail -3 /tmp/pod_h200_followon.log 2>/dev/null
fi
REMOTE
  then
    echo "[ssh error]"
  fi

  echo "========== END REPORT #${N} =========="
  (( SECONDS >= END )) && break
  sleep "$INTERVAL"
done

echo "STATUS_LOOP_COMPLETE reports=${N}"
