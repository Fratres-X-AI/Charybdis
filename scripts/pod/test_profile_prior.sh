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
from collections import Counter
import numpy as np
from scipy.io import netcdf_file
from scripts.prepare_noaa_dem_tile import _finite_grid, _sort_axis, _noaa_elevation_to_depth, _subset_bbox, _project_to_square_grid
from charybdis.hybrid import BathymetryMap, BathymetryProfile, TerrainMatcherConfig, TerrainProfileMatcher

nc = sorted(Path("artifacts/validation").glob("*/highres_bathymetry/noaa_monterey_bay_p080.nc"))[-1]
with netcdf_file(nc, "r") as ds:
    lon = np.asarray(ds.variables["lon"][:], dtype=np.float64)
    lat = np.asarray(ds.variables["lat"][:], dtype=np.float64)
    raw = _finite_grid(ds.variables["Band1"])
lat, raw = _sort_axis(lat, raw, 0)
lon, raw = _sort_axis(lon, raw, 1)
lon, lat, raw = _subset_bbox(lon, lat, raw, -121.893, -121.868, 36.606, 36.644)
depth = _noaa_elevation_to_depth(raw)
proj, extent, res = _project_to_square_grid(lon, lat, np.where(depth>0, depth, np.nan))
mask=np.isfinite(proj); rows=np.where(mask.any(1))[0]; cols=np.where(mask.any(0))[0]
proj=proj[rows[0]:rows[-1]+1, cols[0]:cols[-1]+1]
bmap=BathymetryMap(proj, resolution_m=res)
depth_range=float(np.ptp(proj))
x_min,x_max,y_min,y_max=bmap.bounds_m; margin=8*res; min_relief=max(5.0,0.01*depth_range)

def eval_case(span_mult, prior_mult, no_bias, grid_step):
    span=span_mult*res
    axis=np.linspace(-span, span, 5)
    gxx,gyy=np.meshgrid(axis,axis)
    offsets=np.column_stack((gxx.ravel(),gyy.ravel()))
    cfg=TerrainMatcherConfig(search_radius_m=2*res, grid_step_m=grid_step, prior_weight=0.10,
        min_profile_relief_m=min_relief, max_normalized_cost=6.0,
        min_cost_margin=0.10, ambiguity_separation_m=1.25*res, covariance_cost_window=6.0,
        remove_vertical_bias=no_bias)
    statuses=Counter(); errors=[]
    for seed in range(256):
        rng=np.random.default_rng(seed)
        true_pos=None
        for _ in range(300):
            cand=np.array([rng.uniform(x_min+margin,x_max-margin), rng.uniform(y_min+margin,y_max-margin)])
            depths=bmap.sample(cand+offsets)
            if np.ptp(depths)<min_relief: continue
            true_pos,true_depths=cand,depths; break
        if true_pos is None:
            statuses['skip']+=1; continue
        profile=BathymetryProfile(offsets,true_depths+rng.normal(0,0.75,size=true_depths.shape),variance_m2=(0.75+0.25*res)**2)
        ps=prior_mult*res
        prior=true_pos+rng.normal(0,ps,size=2)
        m=TerrainProfileMatcher(bmap,cfg).match(profile,prior_pos=prior,prior_cov=np.eye(2)*ps**2)
        statuses[m.status.value]+=1
        if m.measurement is not None:
            errors.append(float(np.linalg.norm(m.measurement.pos_fix-true_pos)))
    acc=statuses['accepted']; tried=256-statuses['skip']
    cep95=float(np.percentile(errors,95)) if len(errors)>=2 else float('inf')
    cep50=float(np.percentile(errors,50)) if len(errors)>=2 else float('inf')
    print(f"span={span_mult} prior={prior_mult} bias={no_bias} step={grid_step}: acc={acc}/{tried} ({acc/256:.1%}) cep50={cep50:.2f} cep95={cep95:.2f} {dict(statuses)}")

for span in (2.0, 3.0, 4.0):
  for prior in (0.75, 1.0, 1.5):
    for bias in (True, False):
      eval_case(span, prior, bias, res)
PY
REMOTE
