import numpy as np
import pytest
from charybdis.bathy import load_npz, terrain_from_grid, terrain_suitability
from charybdis.config import SimConfig
from charybdis.terrain import Terrain


def test_terrain_from_grid_roundtrip():
    z = np.random.default_rng(0).random((32, 32)) * 100.0
    t = terrain_from_grid(z, (0.0, 1000.0, 0.0, 1000.0))
    assert isinstance(t, Terrain)
    h = float(t.elevation(500.0, 500.0))
    assert 0.0 <= h <= 100.0


def test_npz_load_roundtrip(tmp_path):
    z = np.sin(np.linspace(0, 4, 64))[:, None] * np.ones((64, 64))
    p = tmp_path / "tile.npz"
    np.savez(p, z=z, extent=np.array([0.0, 8000.0, 0.0, 8000.0]))
    t = load_npz(str(p))
    assert t.grid.shape == (64, 64)


def test_suitability_map_finite():
    cfg = SimConfig(terrain_size=8000.0, terrain_res=200.0)
    m = terrain_suitability(Terrain.synthetic(cfg), cfg, step=400.0)
    assert np.all(np.isfinite(m["score"]))
    assert m["median"] >= 0.0


def test_gebco_netcdf_importorskip(tmp_path):
    netcdf4 = pytest.importorskip("netCDF4")
    p = tmp_path / "fake.nc"
    with netcdf4.Dataset(str(p), "w") as ds:
        ds.createDimension("lat", 4)
        ds.createDimension("lon", 4)
        lat = ds.createVariable("lat", "f8", ("lat",))
        lon = ds.createVariable("lon", "f8", ("lon",))
        elev = ds.createVariable("elevation", "f8", ("lat", "lon"))
        lat[:] = [0, 1, 2, 3]
        lon[:] = [0, 1, 2, 3]
        elev[:, :] = np.arange(16).reshape(4, 4)
    from charybdis.bathy import load_gebco_netcdf

    t = load_gebco_netcdf(str(p))
    assert t.grid.shape == (4, 4)
