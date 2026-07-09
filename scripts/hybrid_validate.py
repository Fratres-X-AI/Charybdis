#!/usr/bin/env python3
"""Run reproducible hybrid harbor Monte Carlo and emit one JSON artifact."""

from __future__ import annotations

import argparse
import os
import subprocess
from dataclasses import asdict
from pathlib import Path

from charybdis.evaluation import (
    VALIDATION_SCENARIOS,
    ValidationManifest,
    assess_validation,
    build_validation_scenario,
    load_validation_seeds,
    run_hybrid_montecarlo,
    validation_gates,
    write_validation_artifact,
)


def _git_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        text=True,
        encoding="utf-8",
    ).strip()


def main() -> int:
    """Parse validation settings, execute fixed seeds, and write JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=8)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--seeds", default="validation/seeds_v1.txt")
    parser.add_argument("--output", default="artifacts/validation/hybrid_mc.json")
    parser.add_argument(
        "--scenario",
        choices=VALIDATION_SCENARIOS,
        default="harbor_nominal",
    )
    args = parser.parse_args()
    if not 2 <= args.runs <= 512:
        parser.error("--runs must be between 2 and 512")
    if not 1 <= args.workers <= 31:
        parser.error("--workers must be between 1 and 31")

    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    seeds = load_validation_seeds(args.seeds, limit=args.runs)
    cfg = build_validation_scenario(args.scenario)
    result = run_hybrid_montecarlo(cfg, seeds=seeds, workers=args.workers)
    gates = validation_gates(args.scenario)
    assessment = assess_validation(result, gates)
    manifest = ValidationManifest(
        git_sha=_git_sha(),
        seeds=seeds,
        workers=args.workers,
        scenario=args.scenario,
        config={
            "runs": args.runs,
            "seed_file": str(Path(args.seeds)),
            "scenario_factory": args.scenario,
        },
    )
    destination = write_validation_artifact(
        args.output,
        manifest=manifest,
        results={
            **result.to_dict(),
            "gates": asdict(gates),
            "assessment": assessment.to_dict(),
        },
    )
    print(destination)
    print(result.to_dict())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
