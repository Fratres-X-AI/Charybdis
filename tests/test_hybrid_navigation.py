import numpy as np

from charybdis import (
    BathymetryMeasurement,
    DepthMeasurement,
    GpsMeasurement,
    HybridFusionConfig,
    HybridNavState,
    HybridSensorFusion,
    ImuMeasurement,
    NavMode,
    PatrolExecutor,
    PatrolRoute,
    SensorPacket,
    VelocityMeasurement,
    Waypoint,
)


def test_hybrid_fusion_transitions_without_position_jump():
    fusion = HybridSensorFusion(
        [0.0, 0.0],
        [1.2, 0.3],
        HybridFusionConfig(init_pos_std=20.0, init_vel_std=1.0),
    )
    true_pos = np.zeros(2)
    true_vel = np.array([1.2, 0.3])
    before_dive = after_dive = None

    for k in range(1, 41):
        true_pos = true_pos + true_vel
        surface = k <= 15
        gps = GpsMeasurement(true_pos, true_vel) if surface else None
        bathy = None
        if not surface and k % 8 == 0:
            bathy = BathymetryMeasurement(
                pos_fix=true_pos,
                pos_cov=np.diag([4.0, 4.0]) ** 2,
            )
        state = fusion.step(SensorPacket(
            imu=ImuMeasurement(np.zeros(2), dt=1.0),
            gps=gps,
            depth=DepthMeasurement(0.2 if surface else 8.0),
            velocity=VelocityMeasurement(true_vel),
            bathymetry=bathy,
        ))
        if k == 15:
            before_dive = state.pos.copy()
        if k == 16:
            after_dive = state.pos.copy()

    assert state.mode == NavMode.SUBMERGED
    assert abs(state.depth_m - 8.0) < 0.5
    assert state.depth_std < 1.0
    assert state.last_gps_t is not None
    assert state.last_bathy_t is not None
    assert np.linalg.norm(after_dive - before_dive) < 2.0
    assert np.linalg.norm(state.pos - true_pos) < 5.0


def test_fusion_rejects_bad_gps_and_uses_bathymetry_feature():
    fusion = HybridSensorFusion([10.0, 0.0], [0.0, 0.0])
    fusion.step(SensorPacket(
        imu=ImuMeasurement(np.zeros(2), dt=1.0),
        gps=GpsMeasurement(np.array([10.0, 0.0])),
        depth=DepthMeasurement(0.0),
    ))
    pos_before = fusion.state().pos.copy()

    fusion.step(SensorPacket(
        imu=ImuMeasurement(np.zeros(2), dt=1.0),
        gps=GpsMeasurement(np.array([1000.0, 1000.0]),
                           pos_cov=np.diag([1.0, 1.0]) ** 2),
        depth=DepthMeasurement(0.0),
    ))
    assert np.linalg.norm(fusion.state().pos - pos_before) < 1.0
    assert fusion.rejections[-1][1] == "gps_pos"

    state = fusion.step(SensorPacket(
        imu=ImuMeasurement(np.zeros(2), dt=1.0),
        depth=DepthMeasurement(10.0),
        bathymetry=BathymetryMeasurement(
            feature_pos=np.array([30.0, 0.0]),
            range_m=20.0,
            bearing_rad=0.0,
            range_var=1.0,
            bearing_var=np.deg2rad(1.0) ** 2,
        ),
    ))
    assert state.mode == NavMode.SUBMERGED
    assert np.linalg.norm(state.pos - np.array([10.0, 0.0])) < 2.0


def test_depth_measurement_is_gated_and_fused():
    fusion = HybridSensorFusion([0.0, 0.0], depth0=2.0)
    s0 = fusion.state()
    state = fusion.step(SensorPacket(
        imu=ImuMeasurement(np.zeros(2), dt=1.0),
        depth=DepthMeasurement(3.0, var=0.25),
    ))
    assert state.depth_m > s0.depth_m
    assert state.depth_std < s0.depth_std

    before = fusion.state().depth_m
    fusion.step(SensorPacket(
        imu=ImuMeasurement(np.zeros(2), dt=1.0),
        depth=DepthMeasurement(100.0, var=0.01),
    ))
    assert abs(fusion.state().depth_m - before) < 1.0
    assert fusion.rejections[-1][1] == "depth"


def test_patrol_executor_handles_surface_and_submerged_segments():
    route = PatrolRoute((
        Waypoint([0.0, 0.0], mode=NavMode.SURFACE, depth_m=0.0),
        Waypoint([20.0, 0.0], mode=NavMode.SUBMERGED, depth_m=8.0, speed_mps=2.0),
        Waypoint([20.0, 20.0], mode=NavMode.SURFACE, depth_m=0.0),
    ))
    patrol = PatrolExecutor(route)
    state = HybridNavState(np.array([0.0, 0.0]), np.zeros(2), np.eye(8),
                           NavMode.SURFACE, t=0.0)

    cmd = patrol.update(state)
    assert cmd.waypoint_index == 1
    assert cmd.target_mode == NavMode.SUBMERGED
    assert cmd.target_depth_m == 8.0
    assert np.allclose(cmd.desired_vel, [2.0, 0.0])
    assert abs(cmd.desired_heading_rad) < 1e-9

    assert patrol.resume(np.array([19.0, 18.0])) == 2
    cmd = patrol.update(HybridNavState(np.array([19.0, 18.0]), np.zeros(2),
                                       np.eye(8), NavMode.SUBMERGED, t=1.0))
    assert cmd.target_mode == NavMode.SURFACE


def test_patrol_arrival_requires_heading_when_requested():
    route = PatrolRoute((
        Waypoint([0.0, 0.0], mode=NavMode.SURFACE),
        Waypoint([10.0, 0.0], heading_rad=0.0, radius_m=2.0,
                 heading_tolerance_rad=0.2),
        Waypoint([20.0, 0.0]),
    ))
    patrol = PatrolExecutor(route)
    patrol.set_index(1)

    wrong_heading = HybridNavState(np.array([10.0, 0.0]), np.array([-1.0, 0.0]),
                                   np.eye(8), NavMode.SURFACE, t=0.0)
    assert patrol.update(wrong_heading).waypoint_index == 1

    good_heading = HybridNavState(np.array([10.0, 0.0]), np.array([1.0, 0.0]),
                                  np.eye(8), NavMode.SURFACE, t=1.0)
    assert patrol.update(good_heading).waypoint_index == 2
