#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/pod_env.sh"
HOST="${POD_HOST#root@}"
ssh -o BatchMode=yes -o ConnectTimeout=12 -p "$POD_PORT" -i "$POD_KEY" "root@$HOST" bash -s <<'EOF'
set +e
echo "=== validation trees ==="
ls -1d /workspace/Charybdis/artifacts/validation/*/ 2>/dev/null
echo "=== full_pass ==="
find /workspace/Charybdis/artifacts/validation -maxdepth 3 -type d -name full_pass 2>/dev/null
find /workspace/Charybdis/artifacts/validation -name 'FULL_PASS*' 2>/dev/null
find /workspace/Charybdis/artifacts/validation -name '*GREEN*' 2>/dev/null | head
echo "=== python cmds ==="
ps -eo pid,etime,args | grep -E 'python' | grep -v grep | grep -v jupyter | head -30
echo "=== last green if any ==="
ls -lt /tmp/pod_pipeline_green* /tmp/*green* 2>/dev/null | head
tail -30 /tmp/pod_post_train_full_pass.log 2>/dev/null
tail -20 /tmp/pod_h200_followon.log 2>/dev/null
EOF
