import numpy as np
import pytest
from charybdis.hybrid import (
    FusionDiagnostics,
    GpsMeasurement,
    HybridFusionConfig,
    HybridNavigator,
    HybridNavState,
    HybridSensorFusion,
    ImuMeasurement,
    ModeManager,
    NavMode,
    PatrolExecutor,
    PatrolRoute,
    SensorPacket,
    SensorQuality,
    VelocityMeasurement,
    Waypoint,
)


def test_sensor_contract_rejects_invalid_covariance_and_quality():
    with pytest.raises(ValueError, match="symmetric"):
        GpsMeasurement([0.0, 0.0], pos_cov=[[1.0, 2.0], [0.0, 1.0]])
    with pytest.raises(ValueError, match="positive semidefinite"):
        VelocityMeasurement([0.0, 0.0], cov=[[1.0, 0.0], [0.0, -1.0]])
    with pytest.raises(ValueError, match="scale"):
        SensorQuality(scale=0.0)


def test_sensor_arrays_are_immutable_snapshots():
    measurement = GpsMeasurement([1.0, 2.0])

    with pytest.raises(ValueError):
        measurement.pos[0] = 9.0
    with pytest.raises(ValueError):
        measurement.pos_cov[0, 0] = 9.0


def test_packet_timestamps_must_be_monotonic():
    fusion = HybridSensorFusion([0.0, 0.0])
    fusion.step(
        SensorPacket(
            imu=ImuMeasurement([0.0, 0.0], 1.0, timestamp_s=2.0),
            timestamp_s=2.0,
        )
    )

    with pytest.raises(ValueError, match="monotonic"):
        fusion.step(
            SensorPacket(
                imu=ImuMeasurement([0.0, 0.0], 1.0, timestamp_s=1.0),
                timestamp_s=1.0,
            )
        )


def test_mode_hint_cannot_override_depth_by_default():
    manager = ModeManager(initial=NavMode.SUBMERGED)

    assert manager.update(depth_m=8.0, hint=NavMode.SURFACE) == NavMode.SUBMERGED
    assert manager.update(depth_m=0.2, hint=NavMode.SUBMERGED) == NavMode.SURFACE
    assert manager.update(depth_m=2.0, hint=NavMode.SUBMERGED) == NavMode.SUBMERGED


def test_rejection_history_is_bounded_and_drives_health():
    fusion = HybridSensorFusion(
        [0.0, 0.0],
        cfg=HybridFusionConfig(
            rejection_history_size=3,
            max_recent_rejections=2,
        ),
    )
    for step in range(5):
        fusion.step(
            SensorPacket(
                imu=ImuMeasurement([0.0, 0.0], 1.0),
                gps=GpsMeasurement(
                    [1000.0, 1000.0],
                    pos_cov=np.eye(2) * 0.01,
                ),
                timestamp_s=float(step + 1),
            )
        )

    state = fusion.state()
    assert len(fusion.rejections) == 3
    assert state.diagnostics.total_rejections == 5
    assert not state.filter_healthy


def test_navigator_fuses_before_generating_guidance():
    class RecordingPatrol(PatrolExecutor):
        seen_state: HybridNavState | None = None

        def update(self, state: HybridNavState):
            self.seen_state = state
            return super().update(state)

    fusion = HybridSensorFusion([0.0, 0.0])
    patrol = RecordingPatrol(PatrolRoute((Waypoint([20.0, 0.0]),)))
    navigator = HybridNavigator(fusion, patrol)

    result = navigator.step(
        SensorPacket(
            imu=ImuMeasurement([0.0, 0.0], 1.0),
            gps=GpsMeasurement([5.0, 0.0], pos_cov=np.eye(2) * 0.01),
        )
    )

    assert patrol.seen_state is result.state
    assert result.state.pos[0] > 4.0
    assert result.command.desired_vel[0] > 0.0


def test_patrol_holds_when_navigation_is_unhealthy():
    state = HybridNavState(
        pos=np.zeros(2),
        vel=np.zeros(2),
        cov=np.eye(8),
        mode=NavMode.SURFACE,
        t=0.0,
        diagnostics=FusionDiagnostics(filter_healthy=False),
    )
    patrol = PatrolExecutor(PatrolRoute((Waypoint([10.0, 0.0]),)))

    command = patrol.update(state)

    assert np.allclose(command.desired_vel, 0.0)


def test_covariance_remains_psd_under_tight_measurements():
    fusion = HybridSensorFusion([0.0, 0.0])
    for _ in range(100):
        fusion.predict(ImuMeasurement([0.01, -0.01], 0.1))
        assert fusion.update_velocity(
            VelocityMeasurement([0.1, -0.1], cov=np.eye(2) * 1e-12)
        )

    covariance = fusion.covariance
    assert np.allclose(covariance, covariance.T)
    assert np.linalg.eigvalsh(covariance).min() > 0.0
