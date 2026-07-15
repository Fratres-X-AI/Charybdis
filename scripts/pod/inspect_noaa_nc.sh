#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
source .venv/bin/activate
python3 - <<'PY'
from pathlib import Path
from scipy.io import netcdf_file
nc = sorted(Path("artifacts/validation").glob("*/highres_bathymetry/noaa_monterey_bay_p080.nc"))[-1]
with netcdf_file(nc, "r") as ds:
    lon = ds.variables["lon"][:]
    lat = ds.variables["lat"][:]
    z = ds.variables["Band1"][:]
print("nc", nc)
print("lon", float(lon.min()), float(lon.max()), lon.size)
print("lat", float(lat.min()), float(lat.max()), lat.size)
print("z shape", z.shape)
PY
REMOTE
