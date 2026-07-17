#!/usr/bin/env bash
# Resume interrupted H200 run on a NEW pod and babysit to green.
# Usage:
#   Edit scripts/pod/pod_env.local.sh with Direct TCP SSH
#   RESUME_MODELS=/path/to/artifacts/.../models bash scripts/pod/resume_h200_finish.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=scripts/pod/pod_env.sh
source "$SCRIPT_DIR/pod_env.sh"

export RESUME_MODELS="${RESUME_MODELS:-$LOCAL_ROOT/artifacts/pod_h200_final_20260717T143729Z/models}"
if [[ ! -d "$RESUME_MODELS" ]]; then
  echo "ERROR: RESUME_MODELS dir missing: $RESUME_MODELS"
  exit 1
fi

echo "=== RESUME H200 FINISH → go_h200_sxm ==="
echo "models_src=$RESUME_MODELS"
exec bash "$SCRIPT_DIR/go_h200_sxm.sh"
