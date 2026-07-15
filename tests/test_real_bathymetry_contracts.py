"""Integration-facing real-bathymetry contract tests."""

from __future__ import annotations

import numpy as np
import pytest
from charybdis.hybrid import BathymetryMap
from scripts.real_bathymetry_validate import (
    INTEGRATION_GRADE_MAX_RESOLUTION_M,
    REAL_BATHYMETRY_SCHEMA_VERSION,
    _build_placement_positions,
    _find_valid_placement,
    _matcher_config_for_map,
    _profile_sampling_for_map,
    _resolution_class,
)


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


def test_relief_biased_placement_finds_sparse_high_relief_cells() -> None:
    depth = np.full((20, 20), 50.0)
    depth[8:12, 8:12] = np.linspace(40.0, 70.0, 16).reshape(4, 4)
    bathymetry_map = BathymetryMap(depth, resolution_m=10.0)
    offsets, _, min_relief = _profile_sampling_for_map(bathymetry_map)
    rng = np.random.default_rng(0)

    position, depths = _find_valid_placement(
        bathymetry_map,
        rng,
        offsets,
        min_relief,
        margin=20.0,
        max_attempts=5,
    )

    assert position is not None
    assert depths is not None
    assert float(np.ptp(depths)) >= min_relief


def test_placement_index_covers_high_relief_interior() -> None:
    depth = np.full((30, 30), 50.0)
    depth[10:20, 10:20] = np.linspace(35.0, 75.0, 100).reshape(10, 10)
    bathymetry_map = BathymetryMap(depth, resolution_m=10.0)
    offsets, _, min_relief = _profile_sampling_for_map(bathymetry_map)
    positions = _build_placement_positions(
        bathymetry_map,
        offsets,
        min_relief,
        margin=20.0,
    )

    assert positions.shape[0] > 0
    for position in positions:
        depths = bathymetry_map.sample(position + offsets)
        assert float(np.ptp(depths)) >= min_relief
