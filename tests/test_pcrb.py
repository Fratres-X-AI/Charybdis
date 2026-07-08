import numpy as np

from charybdis import SimConfig, Terrain, run_simulation
from charybdis.pcrb import (efficiency_report, filter_efficiency,
                            navigability_map, posterior_crb,
                            terrain_fisher_information)
from charybdis.trajectory import generate_truth


def test_terrain_fisher_psd_and_relief():
    cfg = SimConfig()
    flat = Terrain.synthetic(SimConfig(seed=1, terrain_relief=20.0))
    rough = Terrain.synthetic(SimConfig(seed=1, terrain_relief=400.0))
    R = cfg.radar_noise ** 2 + cfg.baro_noise ** 2
    Jf = terrain_fisher_information(flat, 5000.0, 5000.0, R)
    Jr = terrain_fisher_information(rough, 5000.0, 5000.0, R)
    assert np.allclose(Jf, Jf.T)
    assert np.allclose(Jr, Jr.T)
    assert np.all(np.linalg.eigvalsh(Jf) >= -1e-9)
    assert np.trace(Jr) >= np.trace(Jf)


def test_navigability_map_shape_and_relief():
    low = navigability_map(
        Terrain.synthetic(SimConfig(seed=2, terrain_relief=30.0)), SimConfig())
    high = navigability_map(
        Terrain.synthetic(SimConfig(seed=2, terrain_relief=500.0)), SimConfig())
    assert high["score"].shape == (low["score"].shape[0], low["score"].shape[1])
    assert np.all(np.isfinite(high["score"]))
    assert high["median"] >= low["median"]


def test_posterior_crb_sensor_and_bound():
    cfg = SimConfig(duration=60.0, seed=3)
    terrain = Terrain.synthetic(cfg)
    truth = generate_truth(cfg, terrain)
    R_lo = cfg.radar_noise ** 2 + cfg.baro_noise ** 2
    R_hi = 25.0 * R_lo
    crb_lo = posterior_crb(cfg, terrain, truth, R=R_lo)
    crb_hi = posterior_crb(cfg, terrain, truth, R=R_hi)
    assert np.all(np.isfinite(crb_lo)) and np.all(crb_lo > 0)
    h = len(crb_lo) // 2
    assert float(np.mean(crb_lo[h:])) <= float(np.mean(crb_hi[h:])) + 1e-6

    res = run_simulation(cfg)
    rep = efficiency_report(res)
    assert rep["crb_rms_m"] > 0
    assert 0.0 < rep["ekf_efficiency"] <= 1.0
    ekf_rms = rep["ekf_rms_m"]
    assert ekf_rms >= 0.5 * rep["crb_rms_m"]
    assert ekf_rms <= 50.0 * rep["crb_rms_m"]


def test_filter_efficiency_clip():
    assert filter_efficiency(100.0, 50.0) == 0.5
    assert filter_efficiency(0.0, 10.0) == 0.0
