#!/usr/bin/env python3
"""Single-seed preview for a mission-vision scenario."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace

from charybdis.evaluation.mission_scenarios import (
    MISSION_DESCRIPTIONS,
    MISSION_SCENARIOS,
    build_mission_scenario,
    mission_domain,
    mission_spec,
)
from charybdis.simulation import (
    run_hybrid_deep_simulation,
    run_hybrid_harbor_simulation,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        choices=MISSION_SCENARIOS,
        default="shore_beach_landing",
    )
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    spec = mission_spec(args.scenario)
    config = replace(build_mission_scenario(args.scenario), seed=args.seed)
    if mission_domain(args.scenario) == "harbor":
        summary = run_hybrid_harbor_simulation(config).summary()
    else:
        summary = run_hybrid_deep_simulation(config).summary()

    payload = {
        "scenario": args.scenario,
        "domain": spec.domain,
        "description": MISSION_DESCRIPTIONS[args.scenario],
        "seed": args.seed,
        "config": asdict(config),
        "summary": summary,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
