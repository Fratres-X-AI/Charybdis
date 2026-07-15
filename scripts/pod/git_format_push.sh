#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
git add charybdis/evaluation/packet_replay.py scripts/prepare_noaa_dem_tile.py scripts/real_bathymetry_validate.py
git commit -m "$(cat <<'EOF'
Apply ruff formatting to NOAA and bathymetry validation modules.

EOF
)"
git push
gh run list --branch main --limit 2
