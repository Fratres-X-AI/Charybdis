"""Demonstrate unavailable sensors, uncertainty growth, and a guidance hold."""

from __future__ import annotations

import numpy as np
from charybdis import (
    HybridNavigator,
    HybridSensorFusion,
    PatrolExecutor,
    SensorPacket,
)
from charybdis.hybrid import (
    DepthMeasurement,
    GpsMeasurement,
    HybridFusionConfig,
    ImuMeasurement,
    PatrolRoute,
    SensorQuality,
    Waypoint,
)


def main() -> None:
    """Run a deterministic nominal, dropout, and rejected-outlier sequence."""
    fusion = HybridSensorFusion(
        pos0=[0.0, 0.0],
        vel0=[1.0, 0.0],
        cfg=HybridFusionConfig(
            init_pos_std=2.0,
            init_vel_std=0.2,
            max_recent_rejections=0,
        ),
    )
    patrol = PatrolExecutor(
        PatrolRoute((Waypoint([100.0, 0.0], speed_mps=1.0),)),
        max_nav_error_m=20.0,
    )
    navigator = HybridNavigator(fusion, patrol)

    nominal = navigator.step(
        SensorPacket(
            imu=ImuMeasurement([0.0, 0.0], dt=1.0, timestamp_s=1.0),
            gps=GpsMeasurement(
                [1.0, 0.0],
                [1.0, 0.0],
                pos_cov=np.diag([0.2, 0.2]) ** 2,
                vel_cov=np.diag([0.05, 0.05]) ** 2,
                timestamp_s=1.0,
            ),
            depth=DepthMeasurement(0.0, timestamp_s=1.0),
            timestamp_s=1.0,
        )
    )
    nominal_trace = float(np.trace(nominal.state.pos_cov))

    unavailable = SensorQuality(available=False)
    coasted = nominal
    for timestamp in range(2, 6):
        coasted = navigator.step(
            SensorPacket(
                imu=ImuMeasurement(
                    [0.0, 0.0],
                    dt=1.0,
                    timestamp_s=float(timestamp),
                ),
                # Drivers can report a known outage without inventing a valid fix.
                gps=GpsMeasurement(
                    [999.0, 999.0],
                    quality=unavailable,
                    timestamp_s=float(timestamp),
                ),
                depth=DepthMeasurement(0.0, timestamp_s=float(timestamp)),
                timestamp_s=float(timestamp),
            )
        )

    coasted_trace = float(np.trace(coasted.state.pos_cov))
    if coasted.state.diagnostics.total_rejections != 0:
        raise RuntimeError("an unavailable measurement must not count as rejected")
    if coasted_trace <= nominal_trace:
        raise RuntimeError("position uncertainty should grow during GPS dropout")

    faulted = navigator.step(
        SensorPacket(
            imu=ImuMeasurement([0.0, 0.0], dt=1.0, timestamp_s=6.0),
            gps=GpsMeasurement(
                [500.0, 500.0],
                pos_cov=np.diag([0.1, 0.1]) ** 2,
                timestamp_s=6.0,
            ),
            depth=DepthMeasurement(0.0, timestamp_s=6.0),
            timestamp_s=6.0,
        )
    )
    if faulted.state.filter_healthy:
        raise RuntimeError(
            "configured rejection policy should mark the state unhealthy"
        )
    if not np.allclose(faulted.command.desired_vel, 0.0):
        raise RuntimeError("guidance must hold when navigation is unhealthy")

    rejection = faulted.state.diagnostics.recent_rejections[-1]
    print(f"dropout_covariance_trace={coasted_trace:.4f}")
    print(f"rejected_source={rejection.source}")
    print(f"rejected_nis={rejection.nis:.1f} gate={rejection.gate:.1f}")
    print(f"filter_healthy={faulted.state.filter_healthy}")
    print(f"desired_velocity={faulted.command.desired_vel.tolist()}")


if __name__ == "__main__":
    main()
