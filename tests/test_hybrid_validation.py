"""Release-validation scenario and confidence-bound tests."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from charybdis.evaluation import (
    VALIDATION_ARTIFACT_SCHEMA_VERSION,
    VALIDATION_SCENARIOS,
    HybridMonteCarloResult,
    ValidationManifest,
    assess_validation,
    bootstrap_percentile_interval,
    build_validation_scenario,
    validation_gates,
    wilson_interval,
    write_validation_artifact,
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
        max_gps_reacquisition_jump_m=np.zeros(runs),
    )

    assessment = assess_validation(result, validation_gates("harbor_nominal"))

    assert assessment.passed
    assert all(check["passed"] for check in assessment.checks.values())


def test_release_assessment_fails_large_gps_reacquisition_jump() -> None:
    runs = 64
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
        max_gps_reacquisition_jump_m=np.full(runs, 20.0),
    )

    assessment = assess_validation(result, validation_gates("harbor_nominal"))

    assert not assessment.passed
    assert assessment.checks["gps_reacquisition_jump_upper_m"]["passed"] is False


def test_validation_artifact_has_explicit_schema_version(tmp_path: Path) -> None:
    target = tmp_path / "artifact.json"
    manifest = ValidationManifest(
        git_sha="abc123",
        seeds=(1, 2, 3),
        workers=1,
        scenario="harbor_nominal",
    )

    write_validation_artifact(target, manifest=manifest, results={"passed": True})

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["schema_version"] == VALIDATION_ARTIFACT_SCHEMA_VERSION
    assert payload["manifest"]["scenario"] == "harbor_nominal"
    assert payload["results"]["passed"] is True
