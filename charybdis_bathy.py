"""Bathymetry providers for Charybdis.

The engine ships a synthetic map, but a credible simulation should be able to
run against a *real* bathymetric grid (e.g. GEBCO). This module loads a gridded
elevation field from disk and exposes it as a continuous, bilinearly-sampled
callable ``field(x, y)`` compatible with ``charybdis_core.set_bathymetry``.

Supported formats (chosen to stay dependency-light and reproducible):
  * ``.npy``          - a 2-D elevation array
  * ``.npz``          - keys ``z`` (2-D) and optional ``x``/``y`` axes or ``extent``
  * ``.tif/.tiff``    - GeoTIFF, only if ``rasterio`` is installed

If no real data is available the engine simply keeps its synthetic map, so the
rest of the system is unaffected.
"""
from __future__ import annotations

import os
import numpy as np


class GriddedBathymetry:
    """Continuous bilinear sampler over a regular elevation grid.

    ``z[i, j]`` is the elevation at ``(x[j], y[i])`` (row-major, y down the
    first axis). Sampling is vectorised and clamps to the grid edges.
    """

    def __init__(self, z: np.ndarray, extent: tuple[float, float, float, float]):
        self.z = np.asarray(z, dtype=float)
        self.x0, self.x1, self.y0, self.y1 = map(float, extent)
        self.ny, self.nx = self.z.shape
        self.dx = (self.x1 - self.x0) / max(self.nx - 1, 1)
        self.dy = (self.y1 - self.y0) / max(self.ny - 1, 1)

    def __call__(self, x, y):
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        fx = np.clip((x - self.x0) / self.dx, 0, self.nx - 1.0001)
        fy = np.clip((y - self.y0) / self.dy, 0, self.ny - 1.0001)
        x0 = np.floor(fx).astype(int); y0 = np.floor(fy).astype(int)
        x1 = x0 + 1; y1 = y0 + 1
        tx = fx - x0; ty = fy - y0
        z = self.z
        top = z[y0, x0] * (1 - tx) + z[y0, x1] * tx
        bot = z[y1, x0] * (1 - tx) + z[y1, x1] * tx
        return top * (1 - ty) + bot * ty


def load_bathymetry(path: str,
                    extent: tuple[float, float, float, float] | None = None
                    ) -> GriddedBathymetry:
    """Load a bathymetric grid from disk into a continuous sampler."""
    ext = os.path.splitext(path)[1].lower()
    default_extent = extent or (-10.0, 135.0, -10.0, 135.0)

    if ext == ".npy":
        z = np.load(path)
        return GriddedBathymetry(z, default_extent)

    if ext == ".npz":
        d = np.load(path)
        z = d["z"]
        if "extent" in d:
            e = tuple(float(v) for v in d["extent"])
        elif "x" in d and "y" in d:
            e = (float(d["x"].min()), float(d["x"].max()),
                 float(d["y"].min()), float(d["y"].max()))
        else:
            e = default_extent
        return GriddedBathymetry(z, e)

    if ext in (".tif", ".tiff"):
        try:
            import rasterio
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("GeoTIFF support requires 'rasterio'") from exc
        with rasterio.open(path) as ds:  # pragma: no cover - needs a file
            z = ds.read(1).astype(float)
            b = ds.bounds
            return GriddedBathymetry(z, (b.left, b.right, b.bottom, b.top))

    if ext in (".nc", ".netcdf"):
        return load_gebco_netcdf(path, extent=extent)

    raise ValueError(f"Unsupported bathymetry format: {ext}")


def load_gebco_netcdf(path: str,
                      extent: tuple[float, float, float, float] | None = None,
                      lon_var: str = "lon", lat_var: str = "lat",
                      z_var: str = "elevation") -> GriddedBathymetry:
    """Load a GEBCO (or compatible) NetCDF tile into a gridded sampler."""
    try:
        import netCDF4
    except ImportError as exc:
        raise RuntimeError("NetCDF support requires 'netCDF4'") from exc
    with netCDF4.Dataset(path) as ds:  # pragma: no cover - needs file
        lon = np.asarray(ds.variables[lon_var][:], float)
        lat = np.asarray(ds.variables[lat_var][:], float)
        z = np.asarray(ds.variables[z_var][:], float)
        if z.ndim == 3:
            z = z[0]
    e = extent or (float(lon.min()), float(lon.max()),
                   float(lat.min()), float(lat.max()))
    return GriddedBathymetry(z, e)


def export_gebco_region(path: str, out_npz: str, extent: tuple[float, float, float, float],
                          n: int = 200) -> str:
    """Crop/resample a GEBCO NetCDF to a simulation-sized ``.npz`` tile."""
    grid = load_gebco_netcdf(path, extent=extent)
    x0, x1, y0, y1 = extent
    xs = np.linspace(x0, x1, n)
    ys = np.linspace(y0, y1, n)
    gx, gy = np.meshgrid(xs, ys)
    z = grid(gx, gy)
    np.savez(out_npz, z=z, extent=np.array(extent))
    return out_npz


def sample_synthetic_to_grid(func, extent=(-10.0, 135.0, -10.0, 135.0),
                             n: int = 200) -> GriddedBathymetry:
    """Bake any analytic bathymetry callable into a grid (for round-trip use)."""
    x0, x1, y0, y1 = extent
    xs = np.linspace(x0, x1, n)
    ys = np.linspace(y0, y1, n)
    gx, gy = np.meshgrid(xs, ys)
    return GriddedBathymetry(func(gx, gy), extent)
