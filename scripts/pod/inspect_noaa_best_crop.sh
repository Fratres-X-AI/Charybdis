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
depth = -raw
water = depth > 0

best = None
for h_frac in (0.2, 0.25, 0.33, 0.5):
    for w_frac in (0.2, 0.25, 0.33, 0.5):
        h = max(64, int(lat.size * h_frac))
        w = max(64, int(lon.size * w_frac))
        step_i = max(1, h // 8)
        step_j = max(1, w // 8)
        for i0 in range(0, lat.size - h + 1, step_i):
            for j0 in range(0, lon.size - w + 1, step_j):
                sub = water[i0:i0+h, j0:j0+w]
                f = float(sub.mean())
                if f >= 0.85:
                    area = sub.size
                    if best is None or area > best[0]:
                        best = (area, f, lon[j0], lon[j0+w-1], lat[i0], lat[i0+h-1])
print("best", best)
if best:
    _, f, lon0, lon1, lat0, lat1 = best
    print("defaults", lon0, lon1, lat0, lat1, "frac", f)
PY
REMOTE
