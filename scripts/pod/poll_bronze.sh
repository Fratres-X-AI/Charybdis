#!/usr/bin/env bash
HOST=root@213.173.107.32
PORT=37613
KEY="${HOME}/.ssh/id_ed25519"
ssh -o StrictHostKeyChecking=no -p "$PORT" -i "$KEY" "$HOST" <<'REMOTE'
ts() { date -u +"%H:%M:%S"; }
echo "=== $(ts) UTC bronze ==="
echo "cpus=$(nproc) python=$(pgrep -c python || echo 0)"
pgrep -af "pod_bronze_military|hybrid_validate|pod_dual_matrix" || echo "no active procs"
echo "--- military log ---"
tail -n 4 /tmp/pod_bronze_military.log 2>/dev/null || true
echo "--- harbor ---"
tail -n 2 /tmp/pod_harbor_matrix.log 2>/dev/null || true
echo "--- deep ---"
tail -n 2 /tmp/pod_deep_matrix.log 2>/dev/null || true
nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader 2>/dev/null || true
uptime
REMOTE
