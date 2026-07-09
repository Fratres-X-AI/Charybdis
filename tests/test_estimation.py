from dataclasses import replace

import numpy as np
from charybdis.config import SimConfig
from charybdis.estimation import (
    InnovationMonitor,
    covariance_intersection,
    safe_inv,
    stochastic_linearize,
    terrain_meas_var,
)
from charybdis.terrain import Terrain


def test_stochastic_linearization_recovers_planar_gradient():
    cfg = replace(
        SimConfig(),
        terrain_res=1.0,
        ekf_sl_min_frac=0.1,
        ekf_sl_max_radius=5.0,
    )
    axis = np.arange(0.0, 41.0)
    x_grid, y_grid = np.meshgrid(axis, axis)
    terrain = Terrain(2.0 * x_grid - 0.5 * y_grid + 10.0, res=1.0)

    h0, gradient, residual_var = stochastic_linearize(
        terrain,
        np.array([20.0, 20.0]),
        np.diag([4.0, 4.0]),
        cfg,
    )

    np.testing.assert_allclose(h0, 40.0, atol=1e-8)
    assert np.allclose(gradient, [2.0, -0.5], atol=1e-8)
    assert residual_var < 1e-20


def test_terrain_measurement_variance_increases_with_slope():
    cfg = SimConfig(map_interp_frac=0.5)

    flat = terrain_meas_var(cfg, slope=0.0)
    steep = terrain_meas_var(cfg, slope=2.0)

    assert steep > flat > 0.0


def test_innovation_monitor_adapts_and_flags_sustained_fault():
    monitor = InnovationMonitor(window=5, dof=1)
    for _ in range(5):
        monitor.push(9.0)

    assert monitor.q_scale(0.5, 10.0, min_count=5, ema=1.0) == 9.0
    assert monitor.faulted(ratio_thresh=4.0, min_count=5)


def test_safe_inverse_handles_singular_covariance():
    covariance = np.array([[1.0, 1.0], [1.0, 1.0]])

    inverse = safe_inv(covariance)

    assert np.all(np.isfinite(inverse))
    assert np.allclose(covariance @ inverse @ covariance, covariance)


def test_covariance_intersection_is_finite_and_conservative():
    xa = np.array([0.0, 0.0])
    xb = np.array([2.0, 0.0])
    pa = np.eye(2) * 4.0
    pb = np.eye(2)

    fused, covariance, weight = covariance_intersection(xa, pa, xb, pb)

    assert 0.0 < weight < 1.0
    assert 0.0 <= fused[0] <= 2.0
    assert np.linalg.eigvalsh(covariance).min() > 0.0
    assert np.all(np.diag(covariance) >= np.minimum(np.diag(pa), np.diag(pb)))
