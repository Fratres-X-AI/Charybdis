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
from charybdis.bathy import load_bathymetry_map_npz
from charybdis.hybrid import BathymetryProfile, TerrainMatcherConfig, TerrainProfileMatcher
from collections import Counter

tile = sorted(Path("artifacts/validation").glob("*/highres_bathymetry/noaa_monterey_bay_p080.npz"))[-1]
bmap = load_bathymetry_map_npz(tile)
grid = np.asarray(bmap.depth_grid_m, dtype=np.float64)
r = bmap.resolution_m
gy, gx = np.gradient(grid, r)
grad = np.hypot(gx, gy)
print("grad median", np.median(grad), "p90", np.percentile(grad,90), "max", grad.max())

cfg = TerrainMatcherConfig(
    search_radius_m=2.0*r, grid_step_m=r, prior_weight=0.02,
    min_profile_relief_m=max(2.0, 0.005*np.ptp(grid)),
    max_normalized_cost=16.0+(r/50)**2, min_cost_margin=0.02,
    ambiguity_separation_m=1.25*r, covariance_cost_window=8.0,
)

def run(min_relief, min_grad, n=128):
    statuses = Counter()
    errors = []
    span = 2.0*r
    axis = np.array([-span, 0.0, span])
    gxx, gyy = np.meshgrid(axis, axis)
    offsets = np.column_stack((gxx.ravel(), gyy.ravel()))
    x_min, x_max, y_min, y_max = bmap.bounds_m
    margin = 8.0*r
    rows, cols = grid.shape
    for seed in range(n):
        rng = np.random.default_rng(seed + 7000)
        ok = False
        for _ in range(500):
            cand = np.array([rng.uniform(x_min+margin,x_max-margin), rng.uniform(y_min+margin,y_max-margin)])
            depths = bmap.sample(cand + offsets)
            if np.ptp(depths) < min_relief:
                continue
            ix = int(round((cand[0]-bmap.origin_xy_m[0])/r))
            iy = int(round((cand[1]-bmap.origin_xy_m[1])/r))
            ix = np.clip(ix, 0, cols-1); iy = np.clip(iy, 0, rows-1)
            if grad[iy, ix] < min_grad:
                continue
            true_pos, true_depths = cand, depths
            ok = True
            break
        if not ok:
            statuses["skip"] += 1
            continue
        profile = BathymetryProfile(offsets, true_depths + rng.normal(0,0.75,size=true_depths.shape), variance_m2=(0.75+0.25*r)**2)
        prior = true_pos + rng.normal(0, 1.5*r, size=2)
        m = TerrainProfileMatcher(bmap, cfg).match(profile, prior_pos=prior, prior_cov=np.eye(2)*(1.5*r)**2)
        statuses[m.status.value] += 1
        if m.measurement is not None:
            errors.append(float(np.linalg.norm(m.measurement.pos_fix - true_pos)))
    acc = statuses["accepted"]
    cep95 = float(np.percentile(errors, 95)) if len(errors) >= 2 else float("inf")
    print(f"min_relief={min_relief} min_grad={min_grad}: acc={acc}/{n} ({acc/n:.1%}) cep95={cep95:.2f} {dict(statuses)}")

for mr in (5.0, 8.0, 12.0, 15.0):
    for mg in (0.0, 0.05, 0.1, 0.2):
        run(mr, mg)
PY
REMOTE
