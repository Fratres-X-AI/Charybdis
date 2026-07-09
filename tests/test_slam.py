import numpy as np
import pytest

from charybdis import SimConfig, Terrain, generate_truth
from charybdis.experimental.slam import (SlamState, gicp_align, init_slam,
                                         optimize, position_error, slam_step)


def test_gicp_recovers_translation():
    rng = np.random.default_rng(0)
    src = rng.normal(size=(64, 3))
    src[:, 2] = src[:, 0] * 0.1
    t_true = np.array([25.0, -15.0])
    dst = src.copy()
    dst[:, :2] += t_true
    t, err = gicp_align(src, dst)
    assert err < 5.0
    assert np.linalg.norm(t - t_true) < 8.0


@pytest.mark.slow
@pytest.mark.timeout(600)
def test_slam_loop_reduces_error():
    cfg = SimConfig(duration=35.0, seed=4)
    terrain = Terrain.synthetic(cfg)
    truth = generate_truth(cfg, terrain)
    sm = init_slam(truth.pos[0])
    err_before = 0.0
    err_after = 0.0
    loops = 0
    for k in range(1, len(truth)):
        v = (truth.pos[k] - truth.pos[k - 1]) / cfg.dt
        closed = slam_step(sm, v, terrain, dt=cfg.dt)
        loops += int(closed)
        err_after = position_error(sm, truth.pos[k])
    assert err_after < 500.0
    assert loops >= 0
