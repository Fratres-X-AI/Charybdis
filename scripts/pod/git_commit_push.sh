#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

git add \
  README.md \
  charybdis/evaluation/__init__.py \
  charybdis/evaluation/packet_replay.py \
  charybdis/evaluation/validation.py \
  docs/KNOWN_LIMITS.md \
  docs/PRODUCTION_INTEGRATION.md \
  docs/VALIDATION.md \
  docs/INTEGRATION_HANDOFF.md \
  docs/STABLE_API.md \
  scripts/hybrid_validate_deep_matrix.py \
  scripts/hybrid_validate_matrix.py \
  scripts/prepare_noaa_dem_tile.py \
  scripts/real_bathymetry_validate.py \
  scripts/pod/pod_env.sh \
  scripts/pod/launch_highres_bathy.sh \
  scripts/pod/poll_highres_bathy.sh \
  scripts/pod/pull_highres_bathy.sh \
  scripts/pod/pod_highres_bathy.sh \
  scripts/pod/launch_hour_sprint.sh \
  scripts/pod/pod_hour_sprint.sh \
  scripts/pod/poll_hour_sprint.sh \
  scripts/pod/launch_pod_max.sh \
  scripts/pod/pod_max_out.sh \
  scripts/pod/poll_pod_max.sh \
  scripts/pod/pull_integration_grade.sh \
  scripts/pod/pod_status.sh \
  scripts/pod/run_local_tests.sh \
  scripts/pod/tail_max_out.sh \
  scripts/pod/live_updates_30m.sh \
  tests/test_hybrid_replay.py \
  tests/test_hybrid_validation.py \
  tests/test_public_api.py \
  tests/test_prepare_noaa_dem_tile.py \
  tests/test_real_bathymetry_contracts.py

git commit -m "$(cat <<'EOF'
Stabilize integration contracts and pass NOAA high-res matcher validation.

Version replay and validation artifact schemas, document the supported API and handoff bundle, and fix NOAA P080 tile preparation plus integration-grade matcher tuning so pod release characterization passes at ~10 m resolution.
EOF
)"

git status
git push
