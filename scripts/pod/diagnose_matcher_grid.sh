#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
source .venv/bin/activate
export PYTHONPATH=.
python3 - <<'PY'
from collections import Counter
from pathlib import Path
import numpy as np
from charybdis.bathy import load_bathymetry_map_npz
from charybdis.hybrid import BathymetryProfile, TerrainMatcherConfig, TerrainProfileMatcher

tile = sorted(Path("artifacts/validation").glob("*/highres_bathymetry/noaa_monterey_bay_p080.npz"))[-1]
bmap = load_bathymetry_map_npz(tile)
r = bmap.resolution_m
depth_range = float(np.ptp(bmap.depth_grid_m))

configs = {
    "current": TerrainMatcherConfig(
        search_radius_m=2.0*r, grid_step_m=r, prior_weight=0.02,
        min_profile_relief_m=max(2.0, 0.005*depth_range),
        max_normalized_cost=16.0+(r/50)**2, min_cost_margin=0.02,
        ambiguity_separation_m=1.25*r, covariance_cost_window=8.0,
    ),
    "fine2m": TerrainMatcherConfig(
        search_radius_m=30.0, grid_step_m=2.0, prior_weight=0.15,
        min_profile_relief_m=max(3.0, 0.01*depth_range),
        max_normalized_cost=12.0, min_cost_margin=0.15,
        ambiguity_separation_m=5.0, covariance_cost_window=6.0,
    ),
    "fine1m": TerrainMatcherConfig(
        search_radius_m=25.0, grid_step_m=1.0, prior_weight=0.20,
        min_profile_relief_m=max(3.0, 0.01*depth_range),
        max_normalized_cost=10.0, min_cost_margin=0.20,
        ambiguity_separation_m=4.0, covariance_cost_window=5.0,
    ),
    "sim_default": TerrainMatcherConfig(
        search_radius_m=20.0, grid_step_m=2.0, prior_weight=0.25,
        min_profile_relief_m=0.75, max_normalized_cost=9.0,
        min_cost_margin=0.35, ambiguity_separation_m=5.0, covariance_cost_window=6.0,
    ),
}

def eval_cfg(name, cfg, n=128):
    statuses = Counter()
    errors = []
    span = 2.0 * r
    axis = np.array([-span, 0.0, span])
    gx, gy = np.meshgrid(axis, axis)
    offsets = np.column_stack((gx.ravel(), gy.ravel()))
    x_min, x_max, y_min, y_max = bmap.bounds_m
    margin = 8.0 * r
    min_relief = max(3.0, 0.015 * depth_range)
    for seed in range(n):
        rng = np.random.default_rng(seed + 9000)
        true_pos = None
        true_depths = None
        for _ in range(300):
            cand = np.array([rng.uniform(x_min+margin,x_max-margin), rng.uniform(y_min+margin,y_max-margin)])
            depths = bmap.sample(cand + offsets)
            if np.ptp(depths) >= min_relief:
                true_pos, true_depths = cand, depths
                break
        if true_pos is None:
            statuses["no_relief"] += 1
            continue
        profile = BathymetryProfile(offsets, true_depths + rng.normal(0,0.75,size=true_depths.shape), variance_m2=(0.75+0.25*r)**2)
        prior = true_pos + rng.normal(0, 1.5*r, size=2)
        m = TerrainProfileMatcher(bmap, cfg).match(profile, prior_pos=prior, prior_cov=np.eye(2)*(1.5*r)**2)
        statuses[m.status.value] += 1
        if m.measurement is not None:
            errors.append(float(np.linalg.norm(m.measurement.pos_fix - true_pos)))
    acc = statuses["accepted"]
    cep95 = float(np.percentile(errors, 95)) if len(errors) >= 2 else float("inf")
    print(f"{name}: accepted={acc}/{n} ({acc/n:.2%}) cep95={cep95:.2f}m counts={dict(statuses)}")

for name, cfg in configs.items():
    eval_cfg(name, cfg)
PY
REMOTE
