#!/usr/bin/env python3
from __future__ import annotations

from charybdis.evaluation.deep import (
    assess_deep_validation,
    run_hybrid_deep_montecarlo,
)
from charybdis.evaluation.deep_scenarios import (
    DEEP_VALIDATION_SCENARIOS,
    build_deep_validation_scenario,
    deep_validation_gates,
)


def main() -> int:
    for name in DEEP_VALIDATION_SCENARIOS:
        cfg = build_deep_validation_scenario(name)
        result = run_hybrid_deep_montecarlo(cfg, seeds=range(4), workers=1)
        assessment = assess_deep_validation(result, deep_validation_gates(name))
        print(name, "PASS" if assessment.passed else "FAIL")
        print(result.to_dict())
        print(assessment.checks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
