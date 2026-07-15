#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" <<'REMOTE'
cd /workspace/Charybdis
source .venv/bin/activate
export PYTHONPATH=.
python3 - <<'PY'
import json
from pathlib import Path
from collections import Counter
from charybdis.bathy import load_bathymetry_map_npz
from scripts.real_bathymetry_validate import _run_case, _profile_sampling_for_map, _matcher_config_for_map

tile = sorted(Path("artifacts/validation").glob("*/highres_bathymetry/noaa_monterey_bay_p080.npz"))[-1]
bmap = load_bathymetry_map_npz(tile)
cfg = _matcher_config_for_map(bmap)
offsets, prior_sigma, min_relief = _profile_sampling_for_map(bmap)
print("tile", tile)
print("shape", bmap.shape, "res", bmap.resolution_m)
print("cfg", cfg)
print("profile", offsets.shape, "prior_sigma", prior_sigma, "min_relief", min_relief)

cases = [_run_case((bmap, seed)) for seed in range(256)]
print("status", Counter(c["status"] for c in cases))
errors = [c["error_m"] for c in cases if c["error_m"] is not None]
import numpy as np
if errors:
    print("cep50", np.percentile(errors,50), "cep95", np.percentile(errors,95), "n_err", len(errors))

rel = sorted(Path("artifacts/validation").glob("*/highres_bathymetry/release.json"))[-1]
payload = json.loads(rel.read_text())
print("release_file", rel)
print("release_counts", payload["results"]["status_counts"])
print("release_passed", payload["results"]["passed"])
PY
REMOTE
