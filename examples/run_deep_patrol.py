"""Run one deterministic deep-ocean patrol (200-1000 m mission depths)."""

from __future__ import annotations

from charybdis.evaluation import build_deep_validation_scenario
from charybdis.simulation import run_hybrid_deep_simulation


def main() -> None:
    result = run_hybrid_deep_simulation(build_deep_validation_scenario("deep_nominal"))
    summary = result.summary()
    print("deep patrol summary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
