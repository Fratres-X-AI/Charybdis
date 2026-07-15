#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
ruff format charybdis/evaluation/packet_replay.py scripts/prepare_noaa_dem_tile.py scripts/real_bathymetry_validate.py
ruff check charybdis tests scripts examples run_sim.py
ruff format --check charybdis tests scripts examples run_sim.py
