#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
source .venv/bin/activate
export PYTHONPATH=.
TILE=$(ls -t artifacts/validation/*/highres_bathymetry/noaa_monterey_bay_p080.npz 2>/dev/null | head -1)
echo using_tile=$TILE
python3 - <<'PY'
from collections import Counter
from pathlib import Path
import numpy as np
from charybdis.bathy import load_bathymetry_map_npz
from charybdis.hybrid import BathymetryProfile, TerrainMatcherConfig, TerrainProfileMatcher
from scripts.real_bathymetry_validate import _matcher_config_for_map, _run_case

tile = sorted(Path("artifacts/validation").glob("*/highres_bathymetry/noaa_monterey_bay_p080.npz"))[-1]
print("tile", tile)
bmap = load_bathymetry_map_npz(tile)
print("resolution", bmap.resolution_m, "shape", bmap.shape, "depth_ptp", float(np.ptp(bmap.depth_grid_m)))

# baseline
cases = [_run_case((bmap, seed)) for seed in [1,2,3,42,100,200,300,400,500,1000]]
print("baseline", Counter(c["status"] for c in cases))
errs = [c["error_m"] for c in cases if c["error_m"] is not None]
if errs:
    print("baseline errors", np.percentile(errs, 50), np.percentile(errs, 95))

# integration-style config
def integration_cfg(bathymetry_map):
    r = bathymetry_map.resolution_m
    depth_range = float(np.ptp(bathymetry_map.depth_grid_m))
    return TerrainMatcherConfig(
        search_radius_m=max(20.0, 3.0 * r),
        grid_step_m=min(2.0, max(0.5 * r, 1.0)),
        prior_weight=0.25,
        min_profile_relief_m=max(2.0, 0.01 * depth_range),
        max_normalized_cost=9.0,
        min_cost_margin=0.35,
        ambiguity_separation_m=max(3.0, 0.5 * r),
        covariance_cost_window=6.0,
    )

def run_with_cfg(cfg_fn, seeds):
    statuses = []
    errors = []
    for seed in seeds:
        rng = np.random.default_rng(seed)
        r = bmap.resolution_m
        span = 2.0 * r
        axis = np.array([-span, 0.0, span])
        gx, gy = np.meshgrid(axis, axis)
        offsets = np.column_stack((gx.ravel(), gy.ravel()))
        x_min, x_max, y_min, y_max = bmap.bounds_m
        margin = 8.0 * r
        min_relief = max(2.0, 0.01 * float(np.ptp(bmap.depth_grid_m)))
        true_pos = None
        true_depths = None
        for _ in range(200):
            cand = np.array([rng.uniform(x_min+margin,x_max-margin), rng.uniform(y_min+margin,y_max-margin)])
            depths = bmap.sample(cand + offsets)
            if np.ptp(depths) >= min_relief:
                true_pos, true_depths = cand, depths
                break
        if true_pos is None:
            statuses.append("no_relief")
            continue
        profile = BathymetryProfile(offsets, true_depths + rng.normal(0,0.75,size=true_depths.shape), variance_m2=(0.75+0.25*r)**2)
        prior = true_pos + rng.normal(0, 1.5*r, size=2)
        matcher = TerrainProfileMatcher(bmap, cfg_fn(bmap))
        m = matcher.match(profile, prior_pos=prior, prior_cov=np.eye(2)*(1.5*r)**2)
        statuses.append(m.status.value)
        if m.measurement is not None:
            errors.append(float(np.linalg.norm(m.measurement.pos_fix - true_pos)))
    return Counter(statuses), errors

seeds = list(range(1, 65))
print("current_cfg", run_with_cfg(_matcher_config_for_map, seeds))
print("integration_cfg", run_with_cfg(integration_cfg, seeds))
PY
REMOTE
