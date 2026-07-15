#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
source .venv/bin/activate
export PYTHONPATH=.
python3 - <<'PY'
from pathlib import Path
import numpy as np
from scipy.io import netcdf_file
from scripts.prepare_noaa_dem_tile import _finite_grid, _sort_axis, _noaa_elevation_to_depth

nc = sorted(Path("artifacts/validation").glob("*/highres_bathymetry/noaa_monterey_bay_p080.nc"))[-1]
with netcdf_file(nc, "r") as ds:
    lon = np.asarray(ds.variables["lon"][:], dtype=np.float64)
    lat = np.asarray(ds.variables["lat"][:], dtype=np.float64)
    raw = _finite_grid(ds.variables["Band1"])
lat, raw = _sort_axis(lat, raw, 0)
lon, raw = _sort_axis(lon, raw, 1)
depth = _noaa_elevation_to_depth(raw)
water = np.isfinite(depth) & (depth > 0.5)

best = None
for h_frac in (0.1, 0.15, 0.2):
    for w_frac in (0.1, 0.15, 0.2):
        h = max(200, int(lat.size * h_frac))
        w = max(200, int(lon.size * w_frac))
        step_i = max(1, h // 6)
        step_j = max(1, w // 6)
        for i0 in range(0, lat.size - h + 1, step_i):
            for j0 in range(0, lon.size - w + 1, step_j):
                sub = depth[i0:i0+h, j0:j0+w]
                mask = water[i0:i0+h, j0:j0+w]
                if float(mask.mean()) < 0.995:
                    continue
                if not np.all(np.isfinite(sub[mask])):
                    continue
                ptp = float(np.ptp(sub[mask]))
                if ptp < 20.0:
                    continue
                gy, gx = np.gradient(sub, 1.0/3600.0)  # rough deg spacing
                g = np.hypot(gx, gy)
                score = float(np.median(g[mask]))
                if best is None or score > best[0]:
                    best = (score, ptp, lon[j0], lon[j0+w-1], lat[i0], lat[i0+h-1], h, w)
print("best", best)
PY
REMOTE
