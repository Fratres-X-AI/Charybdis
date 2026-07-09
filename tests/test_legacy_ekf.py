from dataclasses import replace

import numpy as np
from charybdis.config import SimConfig
from charybdis.legacy import NavEKF
from charybdis.terrain import Terrain


def _ekf() -> NavEKF:
    cfg = replace(
        SimConfig(),
        terrain_res=1.0,
        adapt_q=False,
        adapt_q_terrain=False,
        ekf_stochastic_lin=False,
        gate_chi2=25.0,
    )
    axis = np.arange(0.0, 101.0)
    x_grid, y_grid = np.meshgrid(axis, axis)
    terrain = Terrain(0.5 * x_grid + 0.25 * y_grid, res=1.0)
    return NavEKF(cfg, terrain, pos0=[50.0, 50.0], vel0=[1.0, 0.0])


def test_legacy_ekf_predict_and_joseph_update_remain_psd():
    ekf = _ekf()

    ekf.predict(np.array([0.1, -0.1]), dt=0.5)
    update = ekf.update_position(
        ekf.pos + np.array([0.5, -0.25]),
        np.eye(2) * 0.5,
    )

    assert update.accepted
    assert np.allclose(ekf.P, ekf.P.T)
    assert np.linalg.eigvalsh(ekf.P).min() >= -1e-10


def test_legacy_ekf_rejects_extreme_position_fix():
    ekf = _ekf()
    before = ekf.pos.copy()

    update = ekf.update_position([10_000.0, 10_000.0], np.eye(2))

    assert not update.accepted
    assert np.allclose(ekf.pos, before)


def test_legacy_ekf_reset_clears_cross_covariance_and_inflates():
    ekf = _ekf()
    ekf.predict(np.array([0.2, 0.1]), dt=1.0)

    ekf.reset_from(
        np.array([20.0, 30.0]),
        np.eye(2) * 4.0,
        vel=np.array([0.5, -0.5]),
        vel_cov=np.eye(2),
        infl=2.0,
    )

    assert np.allclose(ekf.pos, [20.0, 30.0])
    assert np.allclose(ekf.vel, [0.5, -0.5])
    assert np.allclose(ekf.P[0:2, 0:2], np.eye(2) * 8.0)
    assert np.allclose(ekf.P[2:4, 2:4], np.eye(2) * 2.0)
    assert np.allclose(ekf.P[0:4, 4:6], 0.0)
    assert ekf.n_resets == 1
