#!/usr/bin/env bash
set -euo pipefail
cd /workspace/Charybdis
date -u +"=== %H:%M:%S UTC ==="
ps -eo pid,ppid,stat,etime,pcpu,pmem,args | awk '/pod_dual_gpu_max|pod_max_gpu_lane|python -|python3|jupyter/ && !/awk/ {print}'
echo "--- gpu ---"
nvidia-smi --query-gpu=index,utilization.gpu,memory.used,power.draw --format=csv,noheader
echo "--- lane0 last 12 ---"
tail -n 12 /tmp/pod_gpu_lane0.log 2>/dev/null || true
echo "--- lane1 last 12 ---"
tail -n 12 /tmp/pod_gpu_lane1.log 2>/dev/null || true
