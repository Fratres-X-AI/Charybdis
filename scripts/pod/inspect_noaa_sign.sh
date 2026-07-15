#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
source .venv/bin/activate
python3 - <<'PY'
from pathlib import Path
import numpy as np
from scipy.io import netcdf_file
from scripts.prepare_noaa_dem_tile import _finite_grid, _sort_axis

nc = sorted(Path("artifacts/validation").glob("*/highres_bathymetry/noaa_monterey_bay_p080.nc"))[-1]
with netcdf_file(nc, "r") as ds:
    lon = np.asarray(ds.variables["lon"][:], dtype=np.float64)
    lat = np.asarray(ds.variables["lat"][:], dtype=np.float64)
    raw = _finite_grid(ds.variables["Band1"])
lat, raw = _sort_axis(lat, raw, 0)
lon, raw = _sort_axis(lon, raw, 1)
elev_depth = -raw
print("elevation convention underwater", float(np.mean(elev_depth > 0)))
# eastern half lon
mid = lon.size // 2
sub = elev_depth[:, mid:]
print("east half underwater", float(np.mean(sub > 0)))
print("lon east", lon[mid], lon[-1])
PY
REMOTE
