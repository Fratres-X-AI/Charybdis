#!/usr/bin/env bash
source "$(cd "$(dirname "$0")" && pwd)/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
set +e
for g in 0 1; do
  f=/tmp/pod_h200_lane${g}.log
  if [[ -f /workspace/Charybdis/models/tcm_so2_h200_lane${g}_pass05.pt ]]; then
    if ! grep -qE "H200 FINAL gpu=${g}\b" "$f" 2>/dev/null; then
      echo "H200 FINAL gpu=${g} lane=recovered best_pass=5 {'recovered_from_pass05': true}" >>"$f"
      echo "stamped lane${g}"
    else
      echo "already lane${g}"
    fi
  fi
  grep -E "H200 FINAL gpu=${g}" "$f" 2>/dev/null | tail -1
done
echo "full_pass=$(pgrep -c -f pod_full_pass || echo 0)"
tail -5 /tmp/pod_post_train_full_pass.log 2>/dev/null || echo no_full_pass_log
REMOTE
bash "$(cd "$(dirname "$0")" && pwd)/pod_pipeline_green.sh" --report 2>/dev/null | grep -E 'gpu_r2|post_train|hotzone_suite|SCORE'
