import numpy as np
import pytest

from charybdis import SimConfig, Terrain, Tercom, run_simulation
from charybdis.trajectory import generate_truth


@pytest.fixture(scope="module")
def cfg():
    c = SimConfig()
    c.duration = 60.0
    return c


@pytest.fixture(scope="module")
def terrain(cfg):
    return Terrain.synthetic(cfg)


def test_terrain_gradient_matches_finite_difference(terrain):
    x, y = 12_345.0, 9_876.0
    g = terrain.gradient(x, y)
    eps = 5.0
    fd = np.array([
        (terrain.elevation(x + eps, y) - terrain.elevation(x - eps, y)) / (2 * eps),
        (terrain.elevation(x, y + eps) - terrain.elevation(x, y - eps)) / (2 * eps),
    ])
    assert np.allclose(g, fd, atol=0.05)


def test_terrain_interpolation_is_bounded(terrain):
    xs = np.random.default_rng(0).uniform(0, terrain.size, 200)
    ys = np.random.default_rng(1).uniform(0, terrain.size, 200)
    z = terrain.elevation(xs, ys)
    assert z.min() >= terrain.grid.min() - 1e-6
    assert z.max() <= terrain.grid.max() + 1e-6


def test_tercom_recovers_known_offset(cfg, terrain):
    """Feed a shifted strip; TERCOM must recover the negative shift."""
    truth = generate_truth(cfg, terrain)
    tc = Tercom(cfg, terrain)
    shift = np.array([120.0, -90.0])
    for k in range(cfg.tercom_strip):
        p = truth.pos[k]
        elev = float(terrain.elevation(p[0], p[1]))
        tc.push(p + shift, elev)        # est position is offset from truth
    fix = tc.correlate()
    assert fix is not None and fix.valid
    recovered = fix.pos - (truth.pos[cfg.tercom_strip - 1] + shift)
    assert np.linalg.norm(recovered + shift) < cfg.tercom_search_step * 1.5


def test_ekf_beats_unaided_ins():
    cfg = SimConfig()
    cfg.duration = 90.0
    res = run_simulation(cfg)
    s = res.summary()
    assert s["ekf_final_m"] < s["ins_final_m"]
    assert s["ekf_rmse_m"] < 0.15 * s["ins_rmse_m"]
    assert s["ekf_final_m"] < 100.0


def test_filter_consistency():
    cfg = SimConfig()
    cfg.duration = 120.0
    res = run_simulation(cfg)
    sig = np.linalg.norm(res.ekf_std, axis=1)
    frac_within = np.mean(res.ekf_err <= 3 * sig)
    assert frac_within > 0.85
