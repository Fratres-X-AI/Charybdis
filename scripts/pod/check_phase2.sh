#!/usr/bin/env bash
set -euo pipefail

HOST="root@64.247.206.218"
PORT="14049"
KEY="${HOME}/.ssh/id_ed25519"
SSH_OPTS=(-p "$PORT" -i "$KEY" -o StrictHostKeyChecking=no -o BatchMode=yes -T)

ssh "${SSH_OPTS[@]}" "$HOST" 'bash -s' <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
LOG=logs/pod/phase2.log
NOHUP=logs/pod/phase2.nohup
RERUN_LOG=logs/pod/phase2_rerun.log
RERUN_NOHUP=logs/pod/phase2_rerun.nohup

echo "=== check $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "cpus: $(nproc)"

for pair in "$NOHUP:phase2" "$RERUN_NOHUP:phase2_rerun"; do
  nohop="${pair%%:*}"
  label="${pair##*:}"
  if [[ -f "$nohop" ]]; then
    pid=$(cat "$nohop")
    if kill -0 "$pid" 2>/dev/null; then
      echo "status: running ${label} pid=$pid"
    else
      wait_rc=0
      wait "$pid" 2>/dev/null || wait_rc=$?
      echo "status: finished ${label} pid=$pid exit=$wait_rc"
    fi
  fi
done

if [[ ! -f "$NOHUP" && ! -f "$RERUN_NOHUP" ]]; then
  echo "status: not_started"
fi

if pgrep -af "pod_hybrid_phase2.sh" >/dev/null 2>&1; then
  pgrep -af "pod_hybrid_phase2.sh" || true
fi
if pgrep -af "hybrid_validate_matrix.py" >/dev/null 2>&1; then
  pgrep -af "hybrid_validate_matrix.py" || true
fi
if pgrep -af "real_bathymetry_validate.py" >/dev/null 2>&1; then
  pgrep -af "real_bathymetry_validate.py" || true
fi
if pgrep -af "stress_run.py" >/dev/null 2>&1; then
  pgrep -af "stress_run.py" || true
fi

if [[ -f "$RERUN_LOG" ]]; then
  echo "--- rerun tail ---"
  tail -n 15 "$RERUN_LOG" || true
fi
if [[ -f "$LOG" ]]; then
  echo "--- tail ---"
  tail -n 25 "$LOG" || true
  if grep -q "hybrid validation artifacts:" "$LOG" 2>/dev/null; then
    echo "--- result ---"
    grep -E "hybrid validation artifacts:|PASS|FAIL|passed|exit" "$LOG" | tail -n 10 || true
  fi
else
  echo "log: missing"
fi
REMOTE
