#!/usr/bin/env bash
set -euo pipefail
cd /workspace/Charybdis
date -u +"[%H:%M:%S] restart gpu0 lane"

PIDS=$(ps -eo pid,ppid,args | awk '/pod_max_gpu_lane.sh 0 / && !/awk/ {print $1}')
for pid in $PIDS; do
  pkill -P "$pid" || true
  kill "$pid" || true
done
sleep 3

rm -f /tmp/pod_gpu_lane0.log
nohup bash scripts/pod/pod_max_gpu_lane.sh 0 a > /tmp/pod_gpu_lane0_restart.out 2>&1 &
sleep 5
pgrep -af "pod_max_gpu_lane.sh 0|pod_max_gpu_lane.sh 1|pod_dual_gpu_max" || true
nvidia-smi --query-gpu=index,utilization.gpu,memory.used,power.draw --format=csv,noheader
