#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

git add \
  charybdis/evaluation/scenarios.py \
  charybdis/simulation/deep.py \
  scripts/real_bathymetry_validate.py \
  scripts/pod/pod_env.sh \
  scripts/pod/kick_metric_sprint.sh \
  scripts/pod/kick_highres_only.sh \
  scripts/pod/poll_metric_sprint.sh \
  scripts/pod/checkin_metric_sprint.sh \
  scripts/pod/pod_metric_sprint.sh \
  tests/test_real_bathymetry_contracts.py

git commit -m "$(cat <<'EOF'
Improve validation metrics with relief-indexed placement and scenario tuning.

Pre-index integration-grade bathymetry placements at full resolution to eliminate insufficient_relief rejects, tighten harbor outlier/mode-transition gates, and calibrate deep depth covariance.
EOF
)"

git push origin main
git log -1 --oneline
