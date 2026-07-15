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
from scripts.prepare_noaa_dem_tile import _positive_down_depth, _sort_axis

nc = sorted(Path("artifacts/validation").glob("*/highres_bathymetry/noaa_monterey_bay_p080.nc"))[-1]
with netcdf_file(nc, "r") as ds:
    lon = np.asarray(ds.variables["lon"][:], dtype=np.float64)
    lat = np.asarray(ds.variables["lat"][:], dtype=np.float64)
    raw = np.asarray(ds.variables["Band1"][:], dtype=np.float64)
lat, raw = _sort_axis(lat, raw, 0)
lon, raw = _sort_axis(lon, raw, 1)
depth = _positive_down_depth(raw)
water = depth > 0

def frac(i0, i1, j0, j1):
    sub = water[i0:i1, j0:j1]
    return float(sub.mean()), sub.shape

print("full", frac(0, lat.size, 0, lon.size))
# eastern half
mid = lon.size // 2
print("east_half", frac(0, lat.size, mid, lon.size), "lon", lon[mid], lon[-1])
# eastern third
j0 = int(lon.size * 0.66)
print("east_third", frac(0, lat.size, j0, lon.size), "lon", lon[j0], lon[-1])
# southern half eastern
mid_lat = lat.size // 2
print("south_east_quad", frac(mid_lat, lat.size, mid, lon.size))
# scan coarse windows for best >=0.85
best = None
for frac_lat in (0.25, 0.33, 0.5):
    for frac_lon in (0.25, 0.33, 0.5):
        h = max(3, int(lat.size * frac_lat))
        w = max(3, int(lon.size * frac_lon))
        for i0 in range(0, lat.size - h + 1, max(1, h // 4)):
            for j0 in range(0, lon.size - w + 1, max(1, w // 4)):
                f, shape = frac(i0, i0 + h, j0, j0 + w)
                if f >= 0.85:
                    area = shape[0] * shape[1]
                    if best is None or area > best[0]:
                        best = (area, f, i0, i0+h, j0, j0+w, lon[j0], lon[j0+w-1], lat[i0], lat[i0+h-1])
print("best>=0.85", best)
PY
REMOTE
