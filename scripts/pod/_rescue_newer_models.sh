#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/pod_env.sh"
HOST="${POD_HOST#root@}"
DEST="$ROOT/artifacts/pod_h200_final_20260717T191348Z/models"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
DEST2="$ROOT/artifacts/pod_h200_rescue_${STAMP}/models"
mkdir -p "$DEST" "$DEST2"

echo "=== RESCUE newer promoted weights ==="
for f in tcm_so2.pt tcm_so2_best.pt \
  tcm_so2_h200_best_lane0.pt tcm_so2_h200_best_lane1.pt \
  tcm_so2_h200_lane0.pt tcm_so2_h200_lane1.pt \
  tcm_so2_h200_lane0_pass05.pt tcm_so2_h200_lane1_pass05.pt
do
  echo "scp $f"
  scp -o StrictHostKeyChecking=no -o ConnectTimeout=20 -P "$POD_PORT" -i "$POD_KEY" \
    "root@$HOST:/workspace/Charybdis/models/$f" "$DEST2/$f"
  cp -f "$DEST2/$f" "$DEST/$f"
done

echo "=== VERIFY after rescue ==="
for f in tcm_so2.pt tcm_so2_best.pt tcm_so2_h200_best_lane0.pt tcm_so2_h200_best_lane1.pt \
  tcm_so2_h200_lane0_pass05.pt tcm_so2_h200_lane1_pass05.pt
do
  echo -n "LOCAL  "; wc -c "$DEST/$f" | awk '{printf "%s ", $1}'; sha256sum "$DEST/$f"
done

ssh -o BatchMode=yes -o ConnectTimeout=15 -p "$POD_PORT" -i "$POD_KEY" "root@$HOST" bash -s <<'EOF'
cd /workspace/Charybdis/models
for f in tcm_so2.pt tcm_so2_best.pt tcm_so2_h200_best_lane0.pt tcm_so2_h200_best_lane1.pt \
  tcm_so2_h200_lane0_pass05.pt tcm_so2_h200_lane1_pass05.pt
do
  echo -n "REMOTE "; wc -c "$f" | awk '{printf "%s ", $1}'; sha256sum "$f"
done
EOF

echo "RESCUE_DEST=$DEST2"
echo "UPDATED=$DEST"
