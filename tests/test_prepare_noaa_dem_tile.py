"""NOAA DEM preparation contract tests."""

from __future__ import annotations

import numpy as np
import pytest
from scripts.prepare_noaa_dem_tile import (
    _crop_finite_interior,
    _positive_down_depth,
    _sort_axis,
    _subset_bbox,
)


def test_positive_down_depth_converts_elevation_to_depth() -> None:
    elevation_m = np.array([[-10.0, -12.0], [-14.0, 2.0]])

    depth_m = _positive_down_depth(elevation_m)

    assert np.allclose(depth_m, [[10.0, 12.0], [14.0, -2.0]])


def test_positive_down_depth_keeps_positive_depth_grid() -> None:
    depth_m = np.array([[10.0, 12.0], [14.0, -2.0]])

    converted = _positive_down_depth(depth_m)

    assert np.array_equal(converted, depth_m)


def test_sort_axis_reorders_grid_to_increasing_axis() -> None:
    axis = np.array([2.0, 0.0, 1.0])
    grid = np.array([[20.0], [0.0], [10.0]])

    sorted_axis, sorted_grid = _sort_axis(axis, grid, axis_index=0)

    assert np.array_equal(sorted_axis, [0.0, 1.0, 2.0])
    assert np.array_equal(sorted_grid[:, 0], [0.0, 10.0, 20.0])


def test_crop_finite_interior_peels_invalid_border_cells() -> None:
    grid = np.full((5, 5), np.nan)
    grid[1:4, 1:4] = np.arange(9, dtype=np.float64).reshape(3, 3) + 10.0
    extent = np.array([0.0, 40.0, 0.0, 40.0])

    cropped, new_extent = _crop_finite_interior(grid, extent, resolution_m=10.0)

    assert cropped.shape == (3, 3)
    assert np.allclose(new_extent, [10.0, 30.0, 10.0, 30.0])


def test_crop_finite_interior_keeps_valid_underwater_rectangle() -> None:
    grid = np.array(
        [
            [10.0, 11.0, 12.0],
            [13.0, 14.0, 15.0],
            [16.0, 17.0, 18.0],
        ],
        dtype=np.float64,
    )
    extent = np.array([0.0, 20.0, 0.0, 20.0])

    cropped, new_extent = _crop_finite_interior(grid, extent, resolution_m=10.0)

    assert cropped.shape == (3, 3)
    assert np.allclose(new_extent, extent)


def test_subset_bbox_crops_to_offshore_window() -> None:
    longitude = np.linspace(-122.0, -121.7, 8)
    latitude = np.linspace(36.5, 37.0, 6)
    grid = np.zeros((6, 8))

    cropped_lon, cropped_lat, cropped_grid = _subset_bbox(
        longitude,
        latitude,
        grid,
        lon_min=-121.95,
        lon_max=-121.80,
        lat_min=36.55,
        lat_max=36.85,
    )

    assert cropped_lon.size >= 3
    assert cropped_lat.size >= 3
    assert cropped_grid.shape == (cropped_lat.size, cropped_lon.size)


def test_sort_axis_rejects_duplicate_values() -> None:
    with pytest.raises(ValueError, match="strictly monotonic"):
        _sort_axis(np.array([1.0, 1.0, 2.0]), np.zeros((3, 1)), axis_index=0)
