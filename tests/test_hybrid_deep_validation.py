"""Deep-ocean validation scenario and gate tests."""

from __future__ import annotations

import numpy as np
import pytest
from charybdis.evaluation import (
    DEEP_VALIDATION_SCENARIOS,
    HybridMonteCarloResult,
    assess_deep_validation,
    build_deep_validation_scenario,
    deep_validation_gates,
    run_hybrid_deep_montecarlo,
)


def test_all_deep_validation_scenarios_build_with_matching_names() -> None:
    configs = [
        build_deep_validation_scenario(name) for name in DEEP_VALIDATION_SCENARIOS
    ]

    assert [config.name for config in configs] == list(DEEP_VALIDATION_SCENARIOS)
    assert all(config.max_steps >= 800 for config in configs)


def test_unknown_deep_validation_scenario_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown deep validation scenario"):
        build_deep_validation_scenario("not-a-scenario")


@pytest.mark.slow
def test_deep_engineering_matrix_passes_locally() -> None:
    seeds = tuple(range(16))
    for name in DEEP_VALIDATION_SCENARIOS:
        config = build_deep_validation_scenario(name)
        result = run_hybrid_deep_montecarlo(config, seeds=seeds, workers=1)
        assessment = assess_deep_validation(result, deep_validation_gates(name))
        assert assessment.passed, (
            f"{name} failed local engineering gates: {assessment.checks}"
        )


def test_deep_release_assessment_passes_good_sample() -> None:
    runs = 64
    result = HybridMonteCarloResult(
        seeds=tuple(range(runs)),
        final_error_m=np.ones(runs) * 5.0,
        max_error_m=np.ones(runs) * 10.0,
        final_depth_error_m=np.ones(runs) * 0.5,
        position_anees=np.ones(runs),
        depth_anees=np.ones(runs),
        route_complete=np.ones(runs, dtype=np.bool_),
        filter_healthy=np.ones(runs, dtype=np.bool_),
        fusion_rejections=np.zeros(runs, dtype=np.int64),
        max_gps_reacquisition_jump_m=np.zeros(runs),
    )

    assessment = assess_deep_validation(
        result,
        deep_validation_gates("deep_nominal"),
    )

    assert assessment.passed
