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
from scipy.interpolate import RegularGridInterpolator
from scripts.prepare_noaa_dem_tile import (
    _finite_grid, _sort_axis, _subset_bbox, _noaa_elevation_to_depth,
    _axis_metres, DEFAULT_LON_MIN, DEFAULT_LON_MAX, DEFAULT_LAT_MIN, DEFAULT_LAT_MAX,
)

nc = sorted(Path("artifacts/validation").glob("*/highres_bathymetry/noaa_monterey_bay_p080.nc"))[-1]
with netcdf_file(nc, "r") as ds:
    lon = np.asarray(ds.variables["lon"][:], dtype=np.float64)
    lat = np.asarray(ds.variables["lat"][:], dtype=np.float64)
    raw = _finite_grid(ds.variables["Band1"])
lat, raw = _sort_axis(lat, raw, 0)
lon, raw = _sort_axis(lon, raw, 1)
lon, lat, raw = _subset_bbox(lon, lat, raw, DEFAULT_LON_MIN, DEFAULT_LON_MAX, DEFAULT_LAT_MIN, DEFAULT_LAT_MAX)
depth = _noaa_elevation_to_depth(raw)
print("shape", depth.shape, "underwater", float((depth>0).mean()))
print("finite", float(np.isfinite(depth).mean()), "positive", float((depth>0).sum()), "nonpositive", float((depth<=0).sum()))
x_m, y_m = _axis_metres(lon, lat)
resolution_m = float(max(np.median(np.diff(x_m)), np.median(np.diff(y_m))))
projected_x = np.arange(int(x_m[-1] // resolution_m) + 1) * resolution_m
projected_y = np.arange(int(y_m[-1] // resolution_m) + 1) * resolution_m
grid_x, grid_y = np.meshgrid(projected_x, projected_y)
interp = RegularGridInterpolator((y_m, x_m), depth, bounds_error=False, fill_value=np.nan)
proj = interp(np.column_stack((grid_y.ravel(), grid_x.ravel()))).reshape(grid_x.shape)
print("proj shape", proj.shape, "nan_frac", float(np.isnan(proj).mean()))
print("proj underwater among finite", float(np.mean(proj[np.isfinite(proj)] > 0)))
PY
REMOTE
