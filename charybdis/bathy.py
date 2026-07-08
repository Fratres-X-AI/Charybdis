"""Real bathymetry ingestion for the Charybdis airborne GDI stack.

Loads GEBCO NetCDF / NPZ tiles into the core ``Terrain`` type and exposes
terrain suitability (navigability) maps for mission planning.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

import numpy as np

from .config import SimConfig
from .pcrb import navigability_map
from .terrain import Terrain

if TYPE_CHECKING:
    pass


def terrain_from_grid(z: np.ndarray, extent: tuple[float, float, float, float],
                      res: float | None = None) -> Terrain:
    """Build ``Terrain`` from a 2-D elevation array and world extent (x0,x1,y0,y1)."""
    z = np.asarray(z, float)
    x0, x1, y0, y1 = map(float, extent)
    ny, nx = z.shape
    if res is None:
        res = max((x1 - x0) / max(nx - 1, 1), (y1 - y0) / max(ny - 1, 1))
    z = z - z.min()
    return Terrain(grid=z, res=res, origin=(x0, y0))


def load_npz(path: str) -> Terrain:
    """Load ``.npz`` tile with keys ``z`` and ``extent``."""
    d = np.load(path)
    z = d["z"]
    extent = tuple(float(v) for v in d["extent"])
    return terrain_from_grid(z, extent)


def load_gebco_netcdf(path: str,
                      extent: tuple[float, float, float, float] | None = None,
                      lon_var: str = "lon", lat_var: str = "lat",
                      z_var: str = "elevation") -> Terrain:
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
    e = extent or (float(lon.min()), float(lon.max()),
                   float(lat.min()), float(lat.max()))
    return terrain_from_grid(z, e)


def load_bathymetry(path: str,
                    extent: tuple[float, float, float, float] | None = None) -> Terrain:
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


def export_region_to_npz(src_nc: str, out_npz: str,
                         extent: tuple[float, float, float, float],
                         n: int = 256) -> str:
    """Crop/resample GEBCO NetCDF to a simulation-sized NPZ tile."""
    terr = load_gebco_netcdf(src_nc, extent=extent)
    x0, x1, y0, y1 = extent
    xs = np.linspace(x0, x1, n)
    ys = np.linspace(y0, y1, n)
    gx, gy = np.meshgrid(xs, ys)
    z = terr.elevation(gx, gy)
    np.savez(out_npz, z=z, extent=np.array(extent))
    return out_npz


def terrain_suitability(terrain: Terrain, cfg: SimConfig | None = None,
                        step: float | None = None) -> dict:
    """Navigability / suitability map for terrain-aided navigation."""
    return navigability_map(terrain, cfg or SimConfig(), step=step)
