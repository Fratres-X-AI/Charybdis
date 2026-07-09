"""Release-validation scenario and confidence-bound tests."""

from __future__ import annotations

import numpy as np
import pytest
from charybdis.evaluation import (
    VALIDATION_SCENARIOS,
    HybridMonteCarloResult,
    assess_validation,
    bootstrap_percentile_interval,
    build_validation_scenario,
    validation_gates,
    wilson_interval,
)


def test_all_validation_scenarios_build_with_matching_names() -> None:
    configs = [build_validation_scenario(name) for name in VALIDATION_SCENARIOS]

    assert [config.name for config in configs] == list(VALIDATION_SCENARIOS)
    assert all(config.max_steps >= 240 for config in configs)


def test_unknown_validation_scenario_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown validation scenario"):
        build_validation_scenario("not-a-scenario")


def test_wilson_interval_is_bounded_and_conservative() -> None:
    lower, upper = wilson_interval(256, 256)

    assert 0.98 < lower < 1.0
    assert np.isclose(upper, 1.0)
    with pytest.raises(ValueError):
        wilson_interval(2, 1)


def test_bootstrap_interval_is_deterministic() -> None:
    values = np.linspace(0.0, 10.0, 32)

    first = bootstrap_percentile_interval(values, 95.0, resamples=200)
    second = bootstrap_percentile_interval(values, 95.0, resamples=200)

    assert first == second
    assert first[0] <= np.percentile(values, 95.0) <= first[1]


def test_release_assessment_passes_good_sample() -> None:
    runs = 256
    result = HybridMonteCarloResult(
        seeds=tuple(range(runs)),
        final_error_m=np.ones(runs),
        max_error_m=np.ones(runs) * 2.0,
        final_depth_error_m=np.ones(runs) * 0.1,
        position_anees=np.ones(runs),
        depth_anees=np.ones(runs),
        route_complete=np.ones(runs, dtype=np.bool_),
        filter_healthy=np.ones(runs, dtype=np.bool_),
        fusion_rejections=np.zeros(runs, dtype=np.int64),
    )

    assessment = assess_validation(result, validation_gates("harbor_nominal"))

    assert assessment.passed
    assert all(check["passed"] for check in assessment.checks.values())
