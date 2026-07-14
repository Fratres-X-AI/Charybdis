"""Integration-facing real-bathymetry contract tests."""

from __future__ import annotations

import numpy as np
import pytest
from scripts.real_bathymetry_validate import (
    INTEGRATION_GRADE_MAX_RESOLUTION_M,
    REAL_BATHYMETRY_SCHEMA_VERSION,
    _matcher_config_for_map,
    _profile_sampling_for_map,
    _resolution_class,
)
from charybdis.hybrid import BathymetryMap


def test_real_bathymetry_artifact_schema_version_is_named() -> None:
    assert REAL_BATHYMETRY_SCHEMA_VERSION == "1"


def test_real_bathymetry_resolution_classification_is_explicit() -> None:
    assert INTEGRATION_GRADE_MAX_RESOLUTION_M == 50.0
    assert _resolution_class(25.0) == "integration_candidate"
    assert _resolution_class(75.0) == "intermediate_characterization"
    assert _resolution_class(463.0) == "coarse_characterization"


def test_integration_grade_matcher_uses_wider_profile_and_tighter_prior() -> None:
    depth = np.linspace(0.0, 100.0, 100).reshape(10, 10)
    bathymetry_map = BathymetryMap(depth, resolution_m=10.0)
    cfg = _matcher_config_for_map(bathymetry_map)
    offsets, prior_sigma, min_relief = _profile_sampling_for_map(bathymetry_map)

    assert cfg.min_cost_margin == 0.10
    assert cfg.max_normalized_cost == 6.0
    assert offsets.shape == (25, 2)
    assert prior_sigma == 5.0
    assert min_relief == pytest.approx(3.0)
