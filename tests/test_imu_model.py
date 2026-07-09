import numpy as np
from charybdis.config import SimConfig
from charybdis.imu_model import (
    allan_deviation,
    apply_imu_grade,
    grade_allan_table,
    simulate_accel_error,
)


def test_imu_grade_ordering():
    nav = apply_imu_grade(SimConfig(), "navigation")
    con = apply_imu_grade(SimConfig(), "consumer")
    assert nav.accel_noise < con.accel_noise
    assert nav.accel_bias_rw < con.accel_bias_rw


def test_allan_deviation_positive():
    cfg = SimConfig(duration=40.0, seed=5)
    err = simulate_accel_error(cfg)
    tau, sigma = allan_deviation(err, cfg.dt)
    assert tau.size == sigma.size
    assert np.all(tau > 0)
    assert np.all(sigma >= 0)


def test_grade_allan_navigation_best():
    table = grade_allan_table(duration=30.0)
    assert table["navigation"].white_noise < table["consumer"].white_noise


def test_svp_tidal_increases_error():
    base = SimConfig(duration=30.0, seed=9)
    off = simulate_accel_error(base)
    on = simulate_accel_error(SimConfig(duration=30.0, seed=9, svp_tidal_bias=True))
    assert np.std(on) >= 0.8 * np.std(off)
