#!/usr/bin/env python3
"""Download and project a NOAA/NCEI DEM into a positive-down bathymetry tile."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
from scipy.interpolate import RegularGridInterpolator
from scipy.io import netcdf_file

DEFAULT_URL = (
    "https://www.ngdc.noaa.gov/thredds/fileServer/regional/monterey_bay_P080_2018.nc"
)
DEFAULT_SOURCE = "NOAA/NCEI Monterey Bay P080 bathymetric DEM"
# High-relief natural underwater window inside the P080 tile.
DEFAULT_LON_MIN = -121.893
DEFAULT_LON_MAX = -121.868
DEFAULT_LAT_MIN = 36.606
DEFAULT_LAT_MAX = 36.644
EARTH_RADIUS_M = 6_371_000.0


def _as_float_array(value: Any) -> np.ndarray:
    return np.asarray(value, dtype=np.float64)


def _fill_value(variable: Any) -> float | None:
    for name in ("_FillValue", "missing_value"):
        if hasattr(variable, name):
            raw = getattr(variable, name)
            return float(np.asarray(raw).reshape(-1)[0])
    return None


def _finite_grid(variable: Any) -> np.ndarray:
    grid = _as_float_array(variable[:])
    fill = _fill_value(variable)
    if fill is not None:
        grid = np.where(np.isclose(grid, fill), np.nan, grid)
    grid = np.where(np.isfinite(grid), grid, np.nan)
    return grid


def _sort_axis(
    axis: np.ndarray, grid: np.ndarray, axis_index: int
) -> tuple[np.ndarray, np.ndarray]:
    if axis.size < 3:
        raise ValueError("DEM axis is too small")
    order = np.argsort(axis)
    if not np.array_equal(order, np.arange(axis.size)):
        grid = np.take(grid, order, axis=axis_index)
        axis = axis[order]
    if np.any(np.diff(axis) <= 0.0):
        raise ValueError("DEM axes must be strictly monotonic")
    return axis, grid


def _positive_down_depth(elevation_or_depth: np.ndarray) -> np.ndarray:
    """Convert a NOAA DEM grid to positive-down depths using dominant water sign."""
    finite = elevation_or_depth[np.isfinite(elevation_or_depth)]
    if finite.size == 0:
        raise ValueError("DEM grid contains no finite samples")
    negative_fraction = float(np.mean(finite < 0.0))
    positive_fraction = float(np.mean(finite > 0.0))
    if negative_fraction >= positive_fraction:
        return -elevation_or_depth
    return elevation_or_depth


def _noaa_elevation_to_depth(elevation_m: np.ndarray) -> np.ndarray:
    """Convert NOAA MSL elevations to positive-down depths."""
    return -elevation_m


def _auto_underwater_bbox(
    depth_m: np.ndarray,
    longitude: np.ndarray,
    latitude: np.ndarray,
    min_underwater_fraction: float,
) -> tuple[float, float, float, float, float]:
    """Find the largest geographic window that is predominantly underwater."""
    water = depth_m > 0.0
    best: tuple[int, float, int, int, int, int] | None = None
    for height_fraction in (0.2, 0.25, 0.33, 0.5):
        for width_fraction in (0.2, 0.25, 0.33, 0.5):
            height = max(64, int(latitude.size * height_fraction))
            width = max(64, int(longitude.size * width_fraction))
            step_lat = max(1, height // 8)
            step_lon = max(1, width // 8)
            for lat_start in range(0, latitude.size - height + 1, step_lat):
                for lon_start in range(0, longitude.size - width + 1, step_lon):
                    window = water[
                        lat_start : lat_start + height,
                        lon_start : lon_start + width,
                    ]
                    underwater_fraction = float(window.mean())
                    if underwater_fraction < min_underwater_fraction:
                        continue
                    area = window.size
                    if best is None or area > best[0]:
                        best = (
                            area,
                            underwater_fraction,
                            lat_start,
                            lat_start + height,
                            lon_start,
                            lon_start + width,
                        )
    if best is None:
        raise ValueError(
            "unable to find predominantly underwater NOAA crop; "
            f"required >= {min_underwater_fraction:.3f}"
        )
    _, underwater_fraction, lat_start, lat_end, lon_start, lon_end = best
    return (
        float(longitude[lon_start]),
        float(longitude[lon_end - 1]),
        float(latitude[lat_start]),
        float(latitude[lat_end - 1]),
        underwater_fraction,
    )


def _subset_bbox(
    longitude: np.ndarray,
    latitude: np.ndarray,
    grid: np.ndarray,
    lon_min: float,
    lon_max: float,
    lat_min: float,
    lat_max: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Crop a DEM to a geographic bounding box."""
    lon_mask = (longitude >= lon_min) & (longitude <= lon_max)
    lat_mask = (latitude >= lat_min) & (latitude <= lat_max)
    if not np.any(lon_mask) or not np.any(lat_mask):
        raise ValueError(
            "bbox does not intersect NOAA DEM: "
            f"lon=[{lon_min}, {lon_max}] lat=[{lat_min}, {lat_max}]"
        )
    cropped_longitude = longitude[lon_mask]
    cropped_latitude = latitude[lat_mask]
    cropped_grid = grid[np.ix_(lat_mask, lon_mask)]
    if cropped_longitude.size < 3 or cropped_latitude.size < 3:
        raise ValueError("bbox crop is too small for interpolation")
    return cropped_longitude, cropped_latitude, cropped_grid


def _axis_metres(
    longitude: np.ndarray, latitude: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    latitude_origin = float(latitude[0])
    longitude_origin = float(longitude[0])
    latitude_midpoint = float(np.mean(latitude))
    y_m = np.deg2rad(latitude - latitude_origin) * EARTH_RADIUS_M
    x_m = (
        np.deg2rad(longitude - longitude_origin)
        * EARTH_RADIUS_M
        * np.cos(np.deg2rad(latitude_midpoint))
    )
    return x_m, y_m


def _crop_finite_interior(
    projected_depth: np.ndarray,
    extent_m: np.ndarray,
    resolution_m: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Keep the largest fully-valid underwater rectangle after projection."""
    valid = np.isfinite(projected_depth) & (projected_depth > 0.0)
    if not np.any(valid):
        raise ValueError("projected NOAA DEM has no underwater samples")
    rows = np.where(valid.any(axis=1))[0]
    cols = np.where(valid.any(axis=0))[0]
    row_start = int(rows[0])
    row_end = int(rows[-1]) + 1
    col_start = int(cols[0])
    col_end = int(cols[-1]) + 1
    while row_end > row_start and col_end > col_start:
        if valid[row_start:row_end, col_start:col_end].all():
            break
        invalid_top = int(np.count_nonzero(~valid[row_start, col_start:col_end]))
        invalid_bottom = int(np.count_nonzero(~valid[row_end - 1, col_start:col_end]))
        invalid_left = int(np.count_nonzero(~valid[row_start:row_end, col_start]))
        invalid_right = int(np.count_nonzero(~valid[row_start:row_end, col_end - 1]))
        peel = max(
            (invalid_top, "top"),
            (invalid_bottom, "bottom"),
            (invalid_left, "left"),
            (invalid_right, "right"),
        )
        if peel[0] == 0:
            raise ValueError("unable to crop a fully valid NOAA interior")
        if peel[1] == "top":
            row_start += 1
        elif peel[1] == "bottom":
            row_end -= 1
        elif peel[1] == "left":
            col_start += 1
        else:
            col_end -= 1
    cropped = projected_depth[row_start:row_end, col_start:col_end]
    if cropped.shape[0] < 3 or cropped.shape[1] < 3:
        raise ValueError("valid NOAA crop too small after interior peel")
    if np.isnan(cropped).any() or np.any(cropped <= 0.0):
        raise ValueError("projected NOAA DEM interior still contains invalid samples")
    x0 = float(extent_m[0] + col_start * resolution_m)
    y0 = float(extent_m[2] + row_start * resolution_m)
    new_extent = np.array(
        [
            x0,
            x0 + (cropped.shape[1] - 1) * resolution_m,
            y0,
            y0 + (cropped.shape[0] - 1) * resolution_m,
        ],
        dtype=np.float64,
    )
    return cropped, new_extent


def _project_to_square_grid(
    longitude: np.ndarray,
    latitude: np.ndarray,
    depth_m: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float]:
    x_m, y_m = _axis_metres(longitude, latitude)
    underwater_depth = np.where(depth_m > 0.0, depth_m, np.nan)
    resolution_m = float(max(np.median(np.diff(x_m)), np.median(np.diff(y_m))))
    projected_x = np.arange(int(x_m[-1] // resolution_m) + 1) * resolution_m
    projected_y = np.arange(int(y_m[-1] // resolution_m) + 1) * resolution_m
    grid_x, grid_y = np.meshgrid(projected_x, projected_y)
    interpolator = RegularGridInterpolator(
        (y_m, x_m),
        underwater_depth,
        bounds_error=False,
        fill_value=np.nan,
    )
    projected_depth = interpolator(
        np.column_stack((grid_y.ravel(), grid_x.ravel()))
    ).reshape(grid_x.shape)
    extent_m = np.array(
        [0.0, projected_x[-1], 0.0, projected_y[-1]],
        dtype=np.float64,
    )
    if np.isnan(projected_depth).any():
        projected_depth, extent_m = _crop_finite_interior(
            projected_depth,
            extent_m,
            resolution_m,
        )
    return projected_depth, extent_m, resolution_m


def main() -> int:
    """Fetch a NOAA DEM and save a Charybdis-compatible bathymetry NPZ."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--source-name", default=DEFAULT_SOURCE)
    parser.add_argument("--lon-var", default="lon")
    parser.add_argument("--lat-var", default="lat")
    parser.add_argument("--z-var", default="Band1")
    parser.add_argument(
        "--output",
        default="artifacts/validation/noaa_highres/monterey_bay_p080.npz",
    )
    parser.add_argument(
        "--download",
        default="artifacts/validation/noaa_highres/monterey_bay_p080.nc",
    )
    parser.add_argument("--min-underwater-fraction", type=float, default=0.85)
    parser.add_argument(
        "--lon-min",
        type=float,
        default=DEFAULT_LON_MIN,
        help="western longitude bound for offshore crop",
    )
    parser.add_argument(
        "--lon-max",
        type=float,
        default=DEFAULT_LON_MAX,
        help="eastern longitude bound for offshore crop",
    )
    parser.add_argument(
        "--lat-min",
        type=float,
        default=DEFAULT_LAT_MIN,
        help="southern latitude bound for offshore crop",
    )
    parser.add_argument(
        "--lat-max",
        type=float,
        default=DEFAULT_LAT_MAX,
        help="northern latitude bound for offshore crop",
    )
    parser.add_argument(
        "--full-tile",
        action="store_true",
        help="skip offshore crop and use the full NOAA DEM extent",
    )
    parser.add_argument(
        "--auto-crop-underwater",
        action="store_true",
        help="search for the largest predominantly underwater crop",
    )
    args = parser.parse_args()

    if not 0.0 <= args.min_underwater_fraction <= 1.0:
        parser.error("--min-underwater-fraction must be between 0 and 1")

    destination = Path(args.output)
    download = Path(args.download)
    destination.parent.mkdir(parents=True, exist_ok=True)
    download.parent.mkdir(parents=True, exist_ok=True)
    if not download.exists():
        urllib.request.urlretrieve(args.url, download)

    payload = download.read_bytes()
    source_sha256 = hashlib.sha256(payload).hexdigest()
    with netcdf_file(download, mode="r", mmap=False) as dataset:
        longitude = _as_float_array(dataset.variables[args.lon_var][:])
        latitude = _as_float_array(dataset.variables[args.lat_var][:])
        raw_grid = _finite_grid(dataset.variables[args.z_var])

    if raw_grid.shape != (latitude.size, longitude.size):
        raise ValueError(
            f"unexpected DEM dimensions {raw_grid.shape}; "
            f"expected {(latitude.size, longitude.size)}"
        )
    latitude, raw_grid = _sort_axis(latitude, raw_grid, axis_index=0)
    longitude, raw_grid = _sort_axis(longitude, raw_grid, axis_index=1)
    full_longitude = longitude
    full_latitude = latitude
    full_raw_grid = raw_grid
    full_depth_m = _noaa_elevation_to_depth(full_raw_grid)
    crop_bbox = None
    if args.auto_crop_underwater:
        lon_min, lon_max, lat_min, lat_max, _ = _auto_underwater_bbox(
            full_depth_m,
            full_longitude,
            full_latitude,
            args.min_underwater_fraction,
        )
        longitude, latitude, raw_grid = _subset_bbox(
            full_longitude,
            full_latitude,
            full_raw_grid,
            lon_min,
            lon_max,
            lat_min,
            lat_max,
        )
        depth_m = _noaa_elevation_to_depth(raw_grid)
        crop_bbox = {
            "lon_min": lon_min,
            "lon_max": lon_max,
            "lat_min": lat_min,
            "lat_max": lat_max,
            "auto_selected": True,
        }
    elif not args.full_tile:
        longitude, latitude, raw_grid = _subset_bbox(
            full_longitude,
            full_latitude,
            full_raw_grid,
            args.lon_min,
            args.lon_max,
            args.lat_min,
            args.lat_max,
        )
        depth_m = _noaa_elevation_to_depth(raw_grid)
        crop_bbox = {
            "lon_min": args.lon_min,
            "lon_max": args.lon_max,
            "lat_min": args.lat_min,
            "lat_max": args.lat_max,
        }
    else:
        depth_m = full_depth_m
    underwater_fraction = float(np.mean(depth_m > 0.0))
    if (
        underwater_fraction < args.min_underwater_fraction
        and not args.auto_crop_underwater
    ):
        lon_min, lon_max, lat_min, lat_max, underwater_fraction = _auto_underwater_bbox(
            full_depth_m,
            full_longitude,
            full_latitude,
            args.min_underwater_fraction,
        )
        longitude, latitude, raw_grid = _subset_bbox(
            full_longitude,
            full_latitude,
            full_raw_grid,
            lon_min,
            lon_max,
            lat_min,
            lat_max,
        )
        depth_m = _noaa_elevation_to_depth(raw_grid)
        crop_bbox = {
            "lon_min": lon_min,
            "lon_max": lon_max,
            "lat_min": lat_min,
            "lat_max": lat_max,
            "auto_selected": True,
        }
        underwater_fraction = float(np.mean(depth_m > 0.0))
    if underwater_fraction < args.min_underwater_fraction:
        raise ValueError(
            "selected NOAA DEM is not predominantly underwater: "
            f"{underwater_fraction:.3f}"
        )

    projected_depth, extent_m, resolution_m = _project_to_square_grid(
        longitude,
        latitude,
        depth_m,
    )
    np.savez_compressed(
        destination,
        depth_m=projected_depth,
        extent_m=extent_m,
        source_url=np.array(args.url),
        source_sha256=np.array(source_sha256),
    )
    metadata = {
        "source": args.source_name,
        "source_url": args.url,
        "source_sha256": source_sha256,
        "download_bytes": len(payload),
        "crop_bbox": crop_bbox,
        "latitude_range": [float(latitude[0]), float(latitude[-1])],
        "longitude_range": [float(longitude[0]), float(longitude[-1])],
        "raw_shape": list(raw_grid.shape),
        "projected_shape": list(projected_depth.shape),
        "resolution_m": resolution_m,
        "underwater_fraction": underwater_fraction,
        "depth_range_m": [
            float(np.min(projected_depth)),
            float(np.max(projected_depth)),
        ],
        "warning": (
            "Public NOAA DEM validation is integration-candidate evidence only; "
            "it is not safety certification or a sea trial."
        ),
    }
    destination.with_suffix(".json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(destination)
    print(metadata)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
