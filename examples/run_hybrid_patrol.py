"""Run a minimal deterministic surface/submerged patrol."""
from __future__ import annotations

import numpy as np
from charybdis.hybrid import (
    DepthMeasurement,
    GpsMeasurement,
    HybridSensorFusion,
    ImuMeasurement,
    NavMode,
    PatrolExecutor,
    PatrolRoute,
    SensorPacket,
    VelocityMeasurement,
    Waypoint,
)


def main() -> None:
    """Create a route, synthesize measurements, and print mission progress."""
    route = PatrolRoute(
        (
            Waypoint([0.0, 0.0], mode=NavMode.SURFACE, radius_m=1.0),
            Waypoint(
                [10.0, 0.0],
                mode=NavMode.SUBMERGED,
                depth_m=6.0,
                speed_mps=1.0,
                radius_m=1.0,
            ),
            Waypoint(
                [20.0, 0.0],
                mode=NavMode.SURFACE,
                depth_m=0.0,
                speed_mps=1.0,
                radius_m=1.0,
            ),
        )
    )
    fusion = HybridSensorFusion(pos0=[0.0, 0.0])
    patrol = PatrolExecutor(route)

    truth_pos = np.zeros(2)
    truth_vel = np.zeros(2)
    truth_depth = 0.0
    state = fusion.state()

    for step in range(30):
        command = patrol.update(state)
        previous_vel = truth_vel.copy()
        truth_vel = command.desired_vel.copy()
        truth_pos += truth_vel
        truth_depth += 0.25 * (command.target_depth_m - truth_depth)

        gps = None
        velocity = None
        if command.target_mode == NavMode.SURFACE:
            gps = GpsMeasurement(
                pos=truth_pos,
                vel=truth_vel,
                pos_cov=np.eye(2),
                vel_cov=np.eye(2) * 0.01,
            )
        else:
            velocity = VelocityMeasurement(truth_vel, cov=np.eye(2) * 0.01)

        state = fusion.step(
            SensorPacket(
                imu=ImuMeasurement(truth_vel - previous_vel, dt=1.0),
                gps=gps,
                depth=DepthMeasurement(truth_depth, var=0.04),
                velocity=velocity,
                mode_hint=command.target_mode,
            )
        )

        if step % 5 == 0 or command.route_complete:
            print(
                f"step={step:02d} mode={state.mode.value:<9} "
                f"waypoint={command.waypoint_index} "
                f"pos=({state.pos[0]:5.1f}, {state.pos[1]:5.1f}) "
                f"depth={state.depth_m:4.1f} m"
            )
        if command.route_complete:
            break

    print(f"route_complete={patrol.complete}")


if __name__ == "__main__":
    main()
