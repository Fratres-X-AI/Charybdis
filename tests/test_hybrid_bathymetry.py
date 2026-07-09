import numpy as np
import pytest
from charybdis.bathy import bathymetry_map_from_grid
from charybdis.hybrid import (
    BathymetryMap,
    BathymetryProfile,
    MatchStatus,
    TerrainMatcherConfig,
    TerrainProfileMatcher,
)


def _distinctive_map() -> BathymetryMap:
    axis = np.arange(0.0, 101.0)
    x_grid, y_grid = np.meshgrid(axis, axis)
    depth = (
        30.0
        + 4.0 * np.sin(x_grid / 7.0)
        + 3.0 * np.cos(y_grid / 9.0)
        + 2.0 * np.sin((x_grid + y_grid) / 5.0)
    )
    return BathymetryMap(depth, resolution_m=1.0)


def _offsets() -> np.ndarray:
    axis = np.array([-8.0, 0.0, 8.0])
    x_grid, y_grid = np.meshgrid(axis, axis)
    return np.column_stack((x_grid.ravel(), y_grid.ravel()))


def test_profile_match_recovers_distinctive_location():
    bathymetry_map = _distinctive_map()
    true_position = np.array([50.0, 55.0])
    offsets = _offsets()
    profile = BathymetryProfile(
        offsets,
        bathymetry_map.sample(true_position + offsets),
        variance_m2=0.04,
    )
    matcher = TerrainProfileMatcher(
        bathymetry_map,
        TerrainMatcherConfig(
            search_radius_m=15.0,
            grid_step_m=1.0,
            min_cost_margin=0.1,
        ),
    )

    result = matcher.match(
        profile,
        prior_pos=[57.0, 49.0],
        prior_cov=np.diag([10.0, 10.0]) ** 2,
    )

    assert result.status == MatchStatus.ACCEPTED
    assert result.measurement is not None
    assert np.linalg.norm(result.measurement.pos_fix - true_position) <= 1.0
    assert np.linalg.eigvalsh(result.measurement.pos_cov).min() > 0.0
    assert result.cost_margin is not None and result.cost_margin > 0.1


def test_profile_match_rejects_flat_terrain():
    bathymetry_map = BathymetryMap(np.full((50, 50), 20.0), 1.0)
    offsets = _offsets()
    profile = BathymetryProfile(offsets, np.full(offsets.shape[0], 20.0))

    result = TerrainProfileMatcher(bathymetry_map).match(
        profile,
        prior_pos=[25.0, 25.0],
        prior_cov=np.eye(2) * 25.0,
    )

    assert result.status == MatchStatus.INSUFFICIENT_RELIEF
    assert result.measurement is None


def test_profile_match_rejects_out_of_bounds_search():
    bathymetry_map = _distinctive_map()
    offsets = _offsets()
    profile = BathymetryProfile(
        offsets,
        bathymetry_map.sample(np.array([50.0, 50.0]) + offsets),
    )

    result = TerrainProfileMatcher(
        bathymetry_map,
        TerrainMatcherConfig(search_radius_m=2.0, grid_step_m=1.0),
    ).match(
        profile,
        prior_pos=[-100.0, -100.0],
        prior_cov=np.eye(2),
    )

    assert result.status == MatchStatus.OUT_OF_BOUNDS


def test_bathymetry_grid_conversion_preserves_vertical_datum():
    elevation = -np.arange(25, dtype=float).reshape(5, 5)
    bathymetry_map = bathymetry_map_from_grid(
        elevation,
        (0.0, 4.0, 0.0, 4.0),
        values_positive_down=False,
    )

    assert float(bathymetry_map.sample([4.0, 4.0])) == pytest.approx(24.0)


def test_bathymetry_map_arrays_are_immutable():
    bathymetry_map = _distinctive_map()

    with pytest.raises(ValueError):
        bathymetry_map.depth_grid_m[0, 0] = 0.0
