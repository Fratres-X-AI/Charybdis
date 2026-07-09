"""Bathymetry ingestion for legacy terrain and hybrid positive-down maps.

Loads GEBCO NetCDF / NPZ tiles into the core ``Terrain`` type and exposes
terrain suitability (navigability) maps for mission planning.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import ArrayLike

from .config import SimConfig
from .hybrid.bathymetry import BathymetryMap
from .pcrb import navigability_map
from .terrain import Terrain

if TYPE_CHECKING:
    pass


def _extent4(values: ArrayLike) -> tuple[float, float, float, float]:
    extent = np.asarray(values, dtype=np.float64)
    if extent.shape != (4,) or not np.all(np.isfinite(extent)):
        raise ValueError("extent must contain four finite values")
    return (
        float(extent[0]),
        float(extent[1]),
        float(extent[2]),
        float(extent[3]),
    )


def terrain_from_grid(
    z: np.ndarray, extent: tuple[float, float, float, float], res: float | None = None
) -> Terrain:
    """Build ``Terrain`` from a 2-D elevation array and world extent (x0,x1,y0,y1)."""
    z = np.asarray(z, float)
    x0, x1, y0, y1 = map(float, extent)
    ny, nx = z.shape
    if res is None:
        res = max((x1 - x0) / max(nx - 1, 1), (y1 - y0) / max(ny - 1, 1))
    z = z - z.min()
    return Terrain(grid=z, res=res, origin=(x0, y0))


def bathymetry_map_from_grid(
    values: np.ndarray,
    extent_m: tuple[float, float, float, float],
    *,
    values_positive_down: bool,
) -> BathymetryMap:
    """Build a hybrid map without discarding the source vertical datum.

    ``extent_m`` is ``(x_min, x_max, y_min, y_max)`` in a projected local
    metric frame. GEBCO elevation values are positive up, so pass
    ``values_positive_down=False`` to negate them.
    """
    grid = np.asarray(values, dtype=np.float64)
    if grid.ndim != 2 or min(grid.shape) < 3 or not np.all(np.isfinite(grid)):
        raise ValueError("values must be a finite 2D grid at least 3x3")
    x_min, x_max, y_min, y_max = map(float, extent_m)
    if not all(np.isfinite((x_min, x_max, y_min, y_max))):
        raise ValueError("extent_m must be finite")
    if x_max <= x_min or y_max <= y_min:
        raise ValueError("extent_m bounds must be strictly increasing")
    resolution_x = (x_max - x_min) / (grid.shape[1] - 1)
    resolution_y = (y_max - y_min) / (grid.shape[0] - 1)
    if not np.isclose(resolution_x, resolution_y, rtol=1e-6, atol=1e-9):
        raise ValueError("hybrid bathymetry requires square metric grid cells")
    depth = grid if values_positive_down else -grid
    return BathymetryMap(
        depth_grid_m=depth,
        resolution_m=float(resolution_x),
        origin_xy_m=(x_min, y_min),
    )


def load_bathymetry_map_npz(
    path: str,
    *,
    values_positive_down: bool | None = None,
) -> BathymetryMap:
    """Load a projected NPZ tile into the hybrid positive-down map contract.

    Preferred files contain ``depth_m`` and ``extent_m``. Legacy files with
    ``z`` and ``extent`` require an explicit ``values_positive_down`` argument.
    """
    data = np.load(path)
    if "depth_m" in data and "extent_m" in data:
        if values_positive_down is False:
            raise ValueError("depth_m is already positive down")
        return bathymetry_map_from_grid(
            data["depth_m"],
            _extent4(data["extent_m"]),
            values_positive_down=True,
        )
    if "z" not in data or "extent" not in data:
        raise ValueError("NPZ requires depth_m/extent_m or legacy z/extent keys")
    if values_positive_down is None:
        raise ValueError("legacy z tiles require explicit vertical sign semantics")
    return bathymetry_map_from_grid(
        data["z"],
        _extent4(data["extent"]),
        values_positive_down=values_positive_down,
    )


def load_npz(path: str) -> Terrain:
    """Load ``.npz`` tile with keys ``z`` and ``extent``."""
    d = np.load(path)
    z = d["z"]
    extent = _extent4(d["extent"])
    return terrain_from_grid(z, extent)


def load_gebco_netcdf(
    path: str,
    extent: tuple[float, float, float, float] | None = None,
    lon_var: str = "lon",
    lat_var: str = "lat",
    z_var: str = "elevation",
) -> Terrain:
    """Load GEBCO_2024 (or compatible) NetCDF into ``Terrain``."""
    try:
        import netCDF4
    except ImportError as exc:
        raise RuntimeError("NetCDF support requires 'netCDF4'") from exc
    with netCDF4.Dataset(path) as ds:
        lon = np.asarray(ds.variables[lon_var][:], float)
        lat = np.asarray(ds.variables[lat_var][:], float)
        z = np.asarray(ds.variables[z_var][:], float)
        if z.ndim == 3:
            z = z[0]
    e = extent or (
        float(lon.min()),
        float(lon.max()),
        float(lat.min()),
        float(lat.max()),
    )
    return terrain_from_grid(z, e)


def load_bathymetry(
    path: str, extent: tuple[float, float, float, float] | None = None
) -> Terrain:
    """Dispatch loader by file extension (.npz / .npy / .nc)."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".npz":
        return load_npz(path)
    if ext == ".npy":
        z = np.load(path)
        e = extent or (0.0, float(z.shape[1]), 0.0, float(z.shape[0]))
        return terrain_from_grid(z, e)
    if ext in (".nc", ".netcdf"):
        return load_gebco_netcdf(path, extent=extent)
    raise ValueError(f"Unsupported bathymetry format: {ext}")


def export_region_to_npz(
    src_nc: str, out_npz: str, extent: tuple[float, float, float, float], n: int = 256
) -> str:
    """Crop/resample GEBCO NetCDF to a simulation-sized NPZ tile."""
    terr = load_gebco_netcdf(src_nc, extent=extent)
    x0, x1, y0, y1 = extent
    xs = np.linspace(x0, x1, n)
    ys = np.linspace(y0, y1, n)
    gx, gy = np.meshgrid(xs, ys)
    z = terr.elevation(gx, gy)
    np.savez(out_npz, z=z, extent=np.array(extent))
    return out_npz


def terrain_suitability(
    terrain: Terrain, cfg: SimConfig | None = None, step: float | None = None
) -> dict[str, object]:
    """Navigability / suitability map for terrain-aided navigation."""
    return navigability_map(terrain, cfg or SimConfig(), step=step)
