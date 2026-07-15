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
from scripts.prepare_noaa_dem_tile import (
    _finite_grid, _sort_axis, _noaa_elevation_to_depth, _subset_bbox,
    _project_to_square_grid,
)
from charybdis.bathy import load_bathymetry_map_npz
from charybdis.hybrid import BathymetryMap, BathymetryProfile, TerrainMatcherConfig, TerrainProfileMatcher
from scripts.real_bathymetry_validate import _matcher_config_for_map
from collections import Counter

nc = sorted(Path("artifacts/validation").glob("*/highres_bathymetry/noaa_monterey_bay_p080.nc"))[-1]
with netcdf_file(nc, "r") as ds:
    lon = np.asarray(ds.variables["lon"][:], dtype=np.float64)
    lat = np.asarray(ds.variables["lat"][:], dtype=np.float64)
    raw = _finite_grid(ds.variables["Band1"])
lat, raw = _sort_axis(lat, raw, 0)
lon, raw = _sort_axis(lon, raw, 1)

# high-relief natural crop
lon0, lon1, lat0, lat1 = -121.893, -121.868, 36.606, 36.644
lon, lat, raw = _subset_bbox(lon, lat, raw, lon0, lon1, lat0, lat1)
depth = _noaa_elevation_to_depth(raw)
print("crop underwater", float((depth>0).mean()), "ptp", float(np.ptp(depth[depth>0])))

# project without NN fill
underwater = np.where(depth > 0, depth, np.nan)
proj, extent, res = _project_to_square_grid(lon, lat, underwater)
# crop nan edges
mask = np.isfinite(proj)
rows = np.where(mask.any(axis=1))[0]
cols = np.where(mask.any(axis=0))[0]
proj = proj[rows[0]:rows[-1]+1, cols[0]:cols[-1]+1]
print("projected", proj.shape, "res", res, "finite", float(np.isfinite(proj).mean()))
gy, gx = np.gradient(proj, res)
print("proj grad median", float(np.median(np.hypot(gx, gy))))

bmap = BathymetryMap(proj, resolution_m=res)
cfg = _matcher_config_for_map(bmap)
statuses = Counter(); errors = []
span = 2*res; axis = np.array([-span,0,span]); gxx,gyy=np.meshgrid(axis,axis); offsets=np.column_stack((gxx.ravel(),gyy.ravel()))
x_min,x_max,y_min,y_max=bmap.bounds_m; margin=8*res
for seed in range(256):
    rng=np.random.default_rng(seed)
    true_pos=None
    for _ in range(300):
        cand=np.array([rng.uniform(x_min+margin,x_max-margin), rng.uniform(y_min+margin,y_max-margin)])
        depths=bmap.sample(cand+offsets)
        if np.ptp(depths) < max(5.0, 0.01*np.ptp(proj)):
            continue
        true_pos, true_depths = cand, depths
        break
    if true_pos is None:
        statuses['skip']+=1; continue
    profile=BathymetryProfile(offsets, true_depths+rng.normal(0,0.75,size=true_depths.shape), variance_m2=(0.75+0.25*res)**2)
    prior=true_pos+rng.normal(0,1.5*res,size=2)
    m=TerrainProfileMatcher(bmap,cfg).match(profile,prior_pos=prior,prior_cov=np.eye(2)*(1.5*res)**2)
    statuses[m.status.value]+=1
    if m.measurement is not None:
        errors.append(float(np.linalg.norm(m.measurement.pos_fix-true_pos)))
acc=statuses['accepted']
cep95=float(np.percentile(errors,95)) if len(errors)>=2 else float('inf')
print(f"matcher acc={acc}/256 ({acc/256:.1%}) cep95={cep95:.2f} counts={dict(statuses)}")
print(f"gates: need acc>=70% cep95<={1.5*res:.2f}")
PY
REMOTE
