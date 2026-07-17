#!/usr/bin/env python3
"""Download and project a small GEBCO ERDDAP subset for matcher validation."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

import numpy as np
from scipy.interpolate import RegularGridInterpolator
from scipy.io import netcdf_file

DEFAULT_URL = (
    "https://coastwatch.pfeg.noaa.gov/erddap/griddap/GEBCO_2020.nc"
    "?elevation%5B(36.50):1:(36.90)%5D%5B(-122.50):1:(-122.10)%5D"
)
EARTH_RADIUS_M = 6_371_000.0


def gebco_erddap_url(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
) -> str:
    """Build a NOAA ERDDAP subset URL for GEBCO_2020."""
    return (
        "https://coastwatch.pfeg.noaa.gov/erddap/griddap/GEBCO_2020.nc"
        f"?elevation%5B({lat_min}):1:({lat_max})%5D%5B({lon_min}):1:({lon_max})%5D"
    )


def main() -> int:
    """Fetch, project, and save one provenance-tracked bathymetry tile."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument(
        "--output",
        default="artifacts/validation/real_bathymetry/gebco_monterey.npz",
    )
    parser.add_argument(
        "--download",
        default="artifacts/validation/real_bathymetry/gebco_subset.nc",
    )
    parser.add_argument("--lat-min", type=float, default=None)
    parser.add_argument("--lat-max", type=float, default=None)
    parser.add_argument("--lon-min", type=float, default=None)
    parser.add_argument("--lon-max", type=float, default=None)
    parser.add_argument("--min-underwater-fraction", type=float, default=0.95)
    args = parser.parse_args()

    if all(
        v is not None
        for v in (args.lat_min, args.lat_max, args.lon_min, args.lon_max)
    ):
        args.url = gebco_erddap_url(
            args.lat_min, args.lat_max, args.lon_min, args.lon_max
        )

    destination = Path(args.output)
    download = Path(args.download)
    destination.parent.mkdir(parents=True, exist_ok=True)
    download.parent.mkdir(parents=True, exist_ok=True)
    if not download.exists():
        urllib.request.urlretrieve(args.url, download)

    payload = download.read_bytes()
    source_sha256 = hashlib.sha256(payload).hexdigest()
    with netcdf_file(download, mode="r", mmap=False) as dataset:
        latitude = np.asarray(dataset.variables["latitude"][:], dtype=np.float64)
        longitude = np.asarray(dataset.variables["longitude"][:], dtype=np.float64)
        elevation = np.asarray(dataset.variables["elevation"][:], dtype=np.float64)
    if elevation.shape != (latitude.size, longitude.size):
        raise ValueError("unexpected GEBCO subset dimensions")
    if latitude.size < 3 or longitude.size < 3:
        raise ValueError("GEBCO subset is too small")

    latitude_origin = float(latitude[0])
    longitude_origin = float(longitude[0])
    latitude_midpoint = float(np.mean(latitude))
    y_m = np.deg2rad(latitude - latitude_origin) * EARTH_RADIUS_M
    x_m = (
        np.deg2rad(longitude - longitude_origin)
        * EARTH_RADIUS_M
        * np.cos(np.deg2rad(latitude_midpoint))
    )
    resolution_m = float(max(np.median(np.diff(x_m)), np.median(np.diff(y_m))))
    projected_x = np.arange(int(x_m[-1] // resolution_m) + 1) * resolution_m
    projected_y = np.arange(int(y_m[-1] // resolution_m) + 1) * resolution_m
    grid_x, grid_y = np.meshgrid(projected_x, projected_y)
    interpolator = RegularGridInterpolator(
        (y_m, x_m),
        elevation,
        bounds_error=True,
    )
    projected_elevation = interpolator(
        np.column_stack((grid_y.ravel(), grid_x.ravel()))
    ).reshape(grid_x.shape)
    depth_m = -projected_elevation
    underwater_fraction = float(np.mean(depth_m > 0.0))
    if underwater_fraction < args.min_underwater_fraction:
        raise ValueError(
            "selected GEBCO tile is not predominantly underwater: "
            f"{underwater_fraction:.3f} < {args.min_underwater_fraction:.3f}"
        )

    extent_m = np.array(
        [0.0, projected_x[-1], 0.0, projected_y[-1]],
        dtype=np.float64,
    )
    np.savez_compressed(
        destination,
        depth_m=depth_m,
        extent_m=extent_m,
        source_url=np.array(args.url),
        source_sha256=np.array(source_sha256),
    )
    metadata = {
        "source": "GEBCO_2020 via NOAA ERDDAP",
        "source_url": args.url,
        "source_sha256": source_sha256,
        "download_bytes": len(payload),
        "latitude_range": [float(latitude[0]), float(latitude[-1])],
        "longitude_range": [float(longitude[0]), float(longitude[-1])],
        "resolution_m": resolution_m,
        "shape": list(depth_m.shape),
        "depth_range_m": [float(np.min(depth_m)), float(np.max(depth_m))],
        "warning": "GEBCO data is not for navigation or safety-at-sea use.",
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
