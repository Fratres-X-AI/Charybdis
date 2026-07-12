#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import replace

from charybdis.evaluation.deep_scenarios import build_deep_validation_scenario
from charybdis.simulation.deep import run_hybrid_deep_simulation


def main() -> int:
    for name in ("deep_dvl_dropout", "deep_steady_current"):
        print(name)
        base = build_deep_validation_scenario(name)
        for seed in range(8):
            result = run_hybrid_deep_simulation(replace(base, seed=seed))
            summary = result.summary()
            print(seed, summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
