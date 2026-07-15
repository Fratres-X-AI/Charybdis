#!/usr/bin/env bash
# Engineering-tier mission-vision matrix on the active pod.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/pod/pod_env.sh
source "$SCRIPT_DIR/pod_env.sh"

ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" bash -s <<'REMOTE'
set -euo pipefail
cd /workspace/Charybdis
source .venv/bin/activate
python scripts/hybrid_validate_mission_matrix.py \
  --tier engineering \
  --runs 32 \
  --workers 16 \
  --allow-dirty
REMOTE
