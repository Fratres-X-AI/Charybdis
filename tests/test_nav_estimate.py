"""Tests for Navigator.estimate() / NavEstimate (stable autonomy contract)."""

import numpy as np
from charybdis.config import SimConfig
from charybdis.imu import IMU
from charybdis.legacy import NavEstimate, Navigator
from charybdis.terrain import Terrain
from charybdis.trajectory import generate_truth


def test_nav_estimate_ekf_and_pf_have_covariance():
    cfg = SimConfig(duration=5.0, seed=3, use_pf=True, use_pmf=False)
    terrain = Terrain.synthetic(cfg)
    truth = generate_truth(cfg, terrain)
    nav = Navigator(cfg, terrain, truth.pos[0], truth.vel[0])
    imu = IMU(cfg, terrain)
    for k in range(1, min(20, len(truth))):
        s = imu.sample(truth, k)
        nav.step(s, k * cfg.dt)

    est_ekf = nav.estimate("ekf")
    assert isinstance(est_ekf, NavEstimate)
    assert est_ekf.source == "ekf"
    assert est_ekf.pos.shape == (2,)
    assert est_ekf.cov.shape == (2, 2)
    assert np.allclose(est_ekf.cov, est_ekf.cov.T)
    assert est_ekf.error_radius_1sigma > 0.0

    est_pf = nav.estimate("pf")
    assert est_pf.source == "pf"
    assert est_pf.cov.shape == (2, 2)
    assert est_pf.neff is not None and 0 < est_pf.neff <= cfg.n_particles
    assert np.all(np.isfinite(est_pf.pos_std))


def test_nav_estimate_auto_prefers_pmf_when_enabled():
    cfg = SimConfig(duration=3.0, seed=4, use_pf=True, use_pmf=True)
    terrain = Terrain.synthetic(cfg)
    truth = generate_truth(cfg, terrain)
    nav = Navigator(cfg, terrain, truth.pos[0], truth.vel[0])
    imu = IMU(cfg, terrain)
    s = imu.sample(truth, 1)
    nav.step(s, cfg.dt)
    est = nav.estimate("auto")
    assert est.source == "pmf"
    assert est.cov.shape == (2, 2)


def test_pf_pcov_logged_in_arrays():
    cfg = SimConfig(duration=3.0, seed=5, use_pf=True, use_pmf=False)
    terrain = Terrain.synthetic(cfg)
    truth = generate_truth(cfg, terrain)
    nav = Navigator(cfg, terrain, truth.pos[0], truth.vel[0])
    imu = IMU(cfg, terrain)
    for k in range(1, 10):
        nav.step(imu.sample(truth, k), k * cfg.dt)
    arr = nav.arrays()
    assert "pf_pcov" in arr
    assert arr["pf_pcov"].shape[-2:] == (2, 2)
