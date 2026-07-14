#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
python -m pytest tests/test_prepare_noaa_dem_tile.py tests/test_real_bathymetry_contracts.py -q
