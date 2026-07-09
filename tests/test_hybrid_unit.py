import numpy as np
import pytest
from charybdis.hybrid import (
    HybridFusionConfig,
    HybridSensorFusion,
    ImuMeasurement,
    PatrolExecutor,
    PatrolRoute,
    Waypoint,
)


def test_fusion_predict_advances_8d_state():
    fusion = HybridSensorFusion(
        [0.0, 0.0],
        vel0=[1.0, -1.0],
        depth_rate0=2.0,
    )

    fusion.predict(ImuMeasurement([0.5, 0.25], dt=2.0))

    state = fusion.state_vector
    covariance = fusion.covariance
    assert np.allclose(state[fusion.POS], [3.0, -1.5])
    assert np.allclose(state[fusion.VEL], [2.0, -0.5])
    assert state[fusion.DEPTH] == pytest.approx(4.0)
    assert state[fusion.DEPTH_RATE] == pytest.approx(2.0 * np.exp(-0.2))
    assert np.allclose(covariance, covariance.T)
    assert np.linalg.eigvalsh(covariance).min() > 0.0
    with pytest.raises(ValueError):
        state[0] = 1.0


def test_fusion_reset_clamps_velocity_covariance():
    cfg = HybridFusionConfig(init_vel_std=0.4)
    fusion = HybridSensorFusion([0.0, 0.0], vel0=[2.0, -1.0], cfg=cfg)
    for _ in range(5):
        fusion.predict(ImuMeasurement([0.1, -0.1], dt=1.0))
    assert not np.allclose(fusion.covariance[0:2, 3:5], 0.0)
    velocity_before_reset = fusion.state().vel

    state = fusion.reset([4.0, 5.0])

    assert np.allclose(state.vel, velocity_before_reset)
    assert np.allclose(state.cov[3:5, 3:5], np.eye(2) * 0.4**2)
    assert np.allclose(state.cov[0:2, 3:5], 0.0)
    assert np.allclose(state.cov[3:5, 0:2], 0.0)


def test_fusion_reset_depth_block():
    cfg = HybridFusionConfig(init_depth_std=0.8, init_depth_rate_std=0.2)
    fusion = HybridSensorFusion(
        [0.0, 0.0],
        depth0=3.0,
        depth_rate0=1.5,
        cfg=cfg,
    )
    fusion.predict(ImuMeasurement([0.0, 0.0], dt=1.0))

    state = fusion.reset([0.0, 0.0], depth_m=8.0)

    assert state.depth_m == 8.0
    assert state.depth_rate_mps == 0.0
    assert state.cov[fusion.DEPTH, fusion.DEPTH] == pytest.approx(0.8**2)
    assert state.cov[fusion.DEPTH_RATE, fusion.DEPTH_RATE] == pytest.approx(0.2**2)
    assert np.allclose(state.cov[[fusion.DEPTH, fusion.DEPTH_RATE], 0:2], 0.0)


@pytest.mark.parametrize("dt", [0.0, -1.0, np.nan])
def test_fusion_rejects_invalid_imu_dt(dt):
    with pytest.raises(ValueError, match="dt must be finite and positive"):
        ImuMeasurement([0.0, 0.0], dt=dt)


def test_patrol_loop_carrot_uses_last_segment():
    route = PatrolRoute(
        (
            Waypoint([0.0, 0.0], lookahead_m=2.0, radius_m=0.1),
            Waypoint([0.0, 10.0]),
        ),
        loop=True,
    )
    patrol = PatrolExecutor(route)

    carrot = patrol._carrot_target(np.array([0.0, 8.0]), route.waypoints[0])

    assert np.allclose(carrot, [0.0, 6.0])


def test_patrol_carrot_blends_toward_next_segment_without_overshoot():
    route = PatrolRoute(
        (
            Waypoint([0.0, 0.0]),
            Waypoint([10.0, 0.0], lookahead_m=4.0, radius_m=0.1),
            Waypoint([10.0, 10.0]),
        )
    )
    patrol = PatrolExecutor(route)
    patrol.set_index(1)

    carrot = patrol._carrot_target(np.array([10.0, 0.0]), route.waypoints[1])

    assert np.allclose(carrot, [10.0, 4.0])


def test_patrol_turn_rate_holds_heading_at_zero_dt():
    patrol = PatrolExecutor(PatrolRoute((Waypoint([1.0, 0.0]),)))

    assert patrol._limit_heading(0.0, 1.0) == 0.0
    assert patrol._limit_heading(np.pi / 2.0, 1.0) == 0.0


def test_patrol_rejects_negative_turn_rate():
    route = PatrolRoute((Waypoint([1.0, 0.0]),))

    with pytest.raises(ValueError, match="non-negative"):
        PatrolExecutor(route, max_turn_rate_radps=-1.0)
