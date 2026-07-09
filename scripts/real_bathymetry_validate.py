#!/usr/bin/env python3
"""Characterize deterministic terrain matching on a projected real bathymetry tile."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from collections import Counter
from multiprocessing import Pool
from pathlib import Path
from typing import Any

import numpy as np
from charybdis.bathy import load_bathymetry_map_npz
from charybdis.evaluation import (
    bootstrap_percentile_interval,
    load_validation_seeds,
    wilson_interval,
)
from charybdis.hybrid import (
    BathymetryMap,
    BathymetryProfile,
    MatchStatus,
    TerrainMatcherConfig,
    TerrainProfileMatcher,
)


def _git_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        text=True,
        encoding="utf-8",
    ).strip()


def _matcher_config_for_map(bathymetry_map: BathymetryMap) -> TerrainMatcherConfig:
    """Scale matcher tolerances to map resolution (coarse GEBCO needs wider gates)."""
    resolution = bathymetry_map.resolution_m
    depth_range = float(np.ptp(bathymetry_map.depth_grid_m))
    return TerrainMatcherConfig(
        search_radius_m=2.0 * resolution,
        grid_step_m=resolution,
        prior_weight=0.02,
        min_profile_relief_m=max(2.0, 0.005 * depth_range),
        max_normalized_cost=16.0 + (resolution / 50.0) ** 2,
        min_cost_margin=0.02,
        ambiguity_separation_m=1.25 * resolution,
        covariance_cost_window=8.0,
    )


def _cep95_threshold(tier: str, resolution_m: float) -> float:
    """Scale CEP95 gate to map resolution; coarse public tiles are not nav-grade."""
    if resolution_m > 100.0:
        return 4.0 * resolution_m
    return 1.5 * resolution_m


def _acceptance_threshold(tier: str, resolution_m: float) -> float:
    """Conservative lower bound for matcher acceptance on coarse public bathy tiles."""
    if resolution_m > 100.0:
        return 0.20 if tier == "engineering" else 0.30
    return 0.70


def _run_case(job: tuple[BathymetryMap, int]) -> dict[str, Any]:
    bathymetry_map, seed = job
    rng = np.random.default_rng(seed)
    resolution = bathymetry_map.resolution_m
    span = 2.0 * resolution
    axis = np.array([-span, 0.0, span])
    grid_x, grid_y = np.meshgrid(axis, axis)
    profile_offsets = np.column_stack((grid_x.ravel(), grid_y.ravel()))
    x_min, x_max, y_min, y_max = bathymetry_map.bounds_m
    margin = 8.0 * resolution

    noise_std_m = 0.75
    variance_m2 = (noise_std_m + 0.25 * resolution) ** 2

    true_position: np.ndarray | None = None
    true_depths: np.ndarray | None = None
    min_relief = max(2.0, 0.01 * float(np.ptp(bathymetry_map.depth_grid_m)))
    for _ in range(200):
        candidate = np.array(
            [
                rng.uniform(x_min + margin, x_max - margin),
                rng.uniform(y_min + margin, y_max - margin),
            ]
        )
        depths = np.asarray(
            bathymetry_map.sample(candidate + profile_offsets),
            dtype=np.float64,
        )
        if np.ptp(depths) >= min_relief:
            true_position = candidate
            true_depths = depths
            break
    if true_position is None or true_depths is None:
        return {"status": MatchStatus.INSUFFICIENT_RELIEF.value, "error_m": None}

    profile = BathymetryProfile(
        profile_offsets,
        true_depths + rng.normal(0.0, noise_std_m, size=true_depths.shape),
        variance_m2=variance_m2,
    )
    prior_sigma = 1.5 * resolution
    prior = true_position + rng.normal(0.0, prior_sigma, size=2)
    matcher = TerrainProfileMatcher(
        bathymetry_map,
        _matcher_config_for_map(bathymetry_map),
    )
    match = matcher.match(
        profile,
        prior_pos=prior,
        prior_cov=np.eye(2) * prior_sigma**2,
    )
    error_m = None
    if match.measurement is not None:
        matched_position, _ = match.measurement.as_position_fix()
        error_m = float(np.linalg.norm(matched_position - true_position))
    return {
        "status": match.status.value,
        "error_m": error_m,
        "best_cost": match.best_cost,
        "cost_margin": match.cost_margin,
        "candidates_evaluated": match.candidates_evaluated,
    }


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> int:
    """Run real-tile matcher characterization with fixed release gates."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tile", required=True)
    parser.add_argument("--tier", choices=("engineering", "release"), required=True)
    parser.add_argument("--runs", type=int)
    parser.add_argument("--workers", type=int, default=31)
    parser.add_argument("--seeds", default="validation/seeds_v1.txt")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    runs = args.runs or (64 if args.tier == "engineering" else 256)
    if not 2 <= runs <= 512:
        parser.error("--runs must be between 2 and 512")
    if not 1 <= args.workers <= 31:
        parser.error("--workers must be between 1 and 31")

    tile_path = Path(args.tile)
    bathymetry_map = load_bathymetry_map_npz(tile_path)
    seeds = load_validation_seeds(args.seeds, limit=runs)
    started = time.perf_counter()
    jobs = [(bathymetry_map, seed) for seed in seeds]
    if args.workers == 1:
        cases = [_run_case(job) for job in jobs]
    else:
        with Pool(args.workers) as pool:
            cases = pool.map(_run_case, jobs)
    elapsed = time.perf_counter() - started

    statuses = Counter(str(case["status"]) for case in cases)
    errors = np.asarray(
        [float(case["error_m"]) for case in cases if case["error_m"] is not None],
        dtype=np.float64,
    )
    accepted = statuses[MatchStatus.ACCEPTED.value]
    acceptance_interval = wilson_interval(accepted, runs)
    if errors.size >= 2:
        cep95_interval = bootstrap_percentile_interval(errors, 95.0)
        cep95_m = float(np.percentile(errors, 95.0))
    else:
        cep95_interval = (float("inf"), float("inf"))
        cep95_m = float("inf")
    max_cep95_m = _cep95_threshold(args.tier, bathymetry_map.resolution_m)
    acceptance_threshold = _acceptance_threshold(args.tier, bathymetry_map.resolution_m)
    checks = {
        "acceptance_rate_lower": {
            "passed": acceptance_interval[0] >= acceptance_threshold,
            "observed": acceptance_interval[0],
            "threshold": acceptance_threshold,
            "interval_95": list(acceptance_interval),
        },
        "cep95_upper_m": {
            "passed": cep95_interval[1] <= max_cep95_m,
            "observed": cep95_interval[1],
            "threshold": max_cep95_m,
            "interval_95": list(cep95_interval),
        },
    }
    passed = all(bool(check["passed"]) for check in checks.values())
    payload = {
        "manifest": {
            "git_sha": _git_sha(),
            "tier": args.tier,
            "runs": runs,
            "workers": args.workers,
            "seeds": list(seeds),
            "tile": str(tile_path),
            "tile_sha256": hashlib.sha256(tile_path.read_bytes()).hexdigest(),
            "map_shape": list(bathymetry_map.shape),
            "map_resolution_m": bathymetry_map.resolution_m,
        },
        "results": {
            "passed": passed,
            "acceptance_rate": accepted / runs,
            "cep50_m": float(np.percentile(errors, 50.0)) if errors.size else None,
            "cep95_m": cep95_m if np.isfinite(cep95_m) else None,
            "status_counts": dict(sorted(statuses.items())),
            "runtime_s": elapsed,
            "checks": checks,
        },
    }
    output = Path(args.output)
    _atomic_json(output, payload)
    output.with_suffix(".md").write_text(
        "\n".join(
            [
                "# Real bathymetry matcher validation",
                "",
                f"- Result: **{'PASS' if passed else 'FAIL'}**",
                f"- Tier: `{args.tier}`",
                f"- Git SHA: `{payload['manifest']['git_sha']}`",
                f"- Tile SHA-256: `{payload['manifest']['tile_sha256']}`",
                f"- Accepted: `{accepted}/{runs}`",
                f"- CEP95: `{cep95_m:.3f} m`",
                f"- Runtime: `{elapsed:.3f} s`",
                "",
                "GEBCO data and this characterization are not suitable for navigation "
                "or safety-at-sea use.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"real_bathymetry: {'PASS' if passed else 'FAIL'} "
        f"accepted={accepted}/{runs} cep95={cep95_m:.3f}m",
        flush=True,
    )
    return 0 if args.tier == "engineering" or passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
