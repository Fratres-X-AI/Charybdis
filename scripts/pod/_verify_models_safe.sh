#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/pod_env.sh"
HOST="${POD_HOST#root@}"
DEST="$ROOT/artifacts/pod_h200_final_20260717T191348Z"

echo "======== LOCAL ========"
for f in \
  models/tcm_so2.pt \
  models/tcm_so2_best.pt \
  models/tcm_so2_h200_lane0_pass05.pt \
  models/tcm_so2_h200_lane1_pass05.pt \
  models/tcm_so2_h200_best_lane0.pt \
  models/tcm_so2_h200_best_lane1.pt
do
  p="$DEST/$f"
  if [[ -f "$p" ]]; then
    sz=$(wc -c < "$p" | tr -d ' ')
    sha=$(sha256sum "$p" | awk '{print $1}')
    echo "OK  $sz  $sha  $f"
  else
    echo "MISSING  $f"
  fi
done

echo "======== REMOTE ========"
ssh -o BatchMode=yes -o ConnectTimeout=15 -p "$POD_PORT" -i "$POD_KEY" "root@$HOST" bash -s <<'EOF'
set +e
cd /workspace/Charybdis
for f in \
  models/tcm_so2.pt \
  models/tcm_so2_best.pt \
  models/tcm_so2_h200_lane0_pass05.pt \
  models/tcm_so2_h200_lane1_pass05.pt \
  models/tcm_so2_h200_best_lane0.pt \
  models/tcm_so2_h200_best_lane1.pt
do
  if [[ -f "$f" ]]; then
    sz=$(wc -c < "$f" | tr -d ' ')
    sha=$(sha256sum "$f" | awk '{print $1}')
    echo "OK  $sz  $sha  $f"
  else
    echo "MISSING  $f"
  fi
done
echo "--- FULL_PASS ---"
ls -la artifacts/validation/20260717T191623Z-e832541/full_pass/FULL_PASS_* 2>&1
echo "--- GPU ---"
nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader
EOF

echo "======== LOCAL FULL_PASS ========"
find "$DEST/validation" -name 'FULL_PASS*' 2>/dev/null || echo "(no FULL_PASS markers local yet)"
du -sh "$DEST" "$DEST/models" "$DEST/validation" 2>/dev/null || true
