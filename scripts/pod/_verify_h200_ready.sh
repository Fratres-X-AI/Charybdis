#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
chmod +x scripts/pod/*.sh
fail=0
for f in \
  scripts/pod/go_h200_sxm.sh \
  scripts/pod/pod_preflight.sh \
  scripts/pod/ensure_pod_cuda.sh \
  scripts/pod/pod_fast_bootstrap.sh \
  scripts/pod/babysit_h200_elite.sh \
  scripts/pod/pod_pipeline_green.sh \
  scripts/pod/launch_and_babysit.sh \
  scripts/pod/resume_h200_finish.sh \
  scripts/pod/pod_max_gpu_lane.sh \
  scripts/pod/pod_h200_max_gpu_lane.sh \
  scripts/pod/pod_h200_followon.sh \
  scripts/pod/pod_quad_gpu_max.sh \
  scripts/pod/pull_h200_shutdown.sh
do
  if bash -n "$f"; then
    echo "OK $f"
  else
    echo "FAIL $f"
    fail=1
  fi
done

echo "--- preflight (expect configure error, not syntax crash) ---"
set +e
bash scripts/pod/pod_preflight.sh
rc=$?
set -e
echo "preflight_exit=$rc"

MODELS=artifacts/pod_h200_final_20260717T143729Z/models
if [[ -d "$MODELS" ]]; then
  n=$(ls "$MODELS"/tcm_so2*.pt 2>/dev/null | wc -l)
  echo "RESUME_MODELS_OK count=$n"
else
  echo "RESUME_MODELS_MISSING"
  fail=1
fi

if [[ -f scripts/pod/pod_env.local.sh.example ]]; then
  echo "ENV_EXAMPLE_OK"
else
  echo "ENV_EXAMPLE_MISSING"
  fail=1
fi

exit "$fail"
