#!/usr/bin/env bash
# Launch remote CPU validation, bathymetry characterization, and follow-on GPU checks.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

bash "$SCRIPT_DIR/kick_saturate_h200.sh"
bash "$SCRIPT_DIR/kick_hotzone_bathy.sh"
