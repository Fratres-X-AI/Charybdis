"""Wire HybridNavigator between a sensor adapter and a command consumer.

The adapter below is deterministic simulation code. A vehicle integration
would replace it with calibrated drivers and a separately supervised controller.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from charybdis import (
    HybridNavigator,
    HybridSensorFusion,
    NavMode,
    PatrolExecutor,
    SensorPacket,
)
from charybdis.hybrid import (
    DepthMeasurement,
    GpsMeasurement,
    ImuMeasurement,
    PatrolCommand,
    PatrolRoute,
    VelocityMeasurement,
    Waypoint,
)


@dataclass
class DeterministicVehicleAdapter:
    """Stand-in for synchronized sensor drivers and a vehicle controller."""

    pos: np.ndarray
    vel: np.ndarray
    depth_m: float = 0.0
    dt: float = 1.0

    def cycle(
        self,
        command: PatrolCommand | None,
        *,
        timestamp_s: float,
    ) -> SensorPacket:
        """Apply the last command and return one coherent sensor packet."""
        previous_velocity = self.vel.copy()
        if command is not None:
            self.vel = command.desired_vel.copy()
            self.pos += self.vel * self.dt
            depth_error = command.target_depth_m - self.depth_m
            self.depth_m += float(np.clip(depth_error, -0.5, 0.5))

        acceleration = (self.vel - previous_velocity) / self.dt
        surfaced = self.depth_m <= 1.5
        gps = (
            GpsMeasurement(
                pos=self.pos,
                vel=self.vel,
                pos_cov=np.diag([0.8, 0.8]) ** 2,
                vel_cov=np.diag([0.05, 0.05]) ** 2,
                timestamp_s=timestamp_s,
            )
            if surfaced
            else None
        )
        velocity = (
            None
            if surfaced
            else VelocityMeasurement(
                self.vel,
                cov=np.diag([0.05, 0.05]) ** 2,
                timestamp_s=timestamp_s,
            )
        )
        return SensorPacket(
            imu=ImuMeasurement(
                acceleration,
                dt=self.dt,
                timestamp_s=timestamp_s,
            ),
            gps=gps,
            depth=DepthMeasurement(
                self.depth_m,
                var=0.5**2,
                timestamp_s=timestamp_s,
            ),
            velocity=velocity,
            mode_hint=None if command is None else command.target_mode,
            timestamp_s=timestamp_s,
        )


def build_navigator() -> HybridNavigator:
    """Create the estimator and route-following components."""
    route = PatrolRoute(
        (
            Waypoint(
                [10.0, 0.0],
                mode=NavMode.SURFACE,
                radius_m=1.0,
                speed_mps=1.0,
            ),
            Waypoint(
                [22.0, 0.0],
                mode=NavMode.SUBMERGED,
                depth_m=6.0,
                radius_m=1.0,
                speed_mps=1.0,
            ),
            Waypoint(
                [34.0, 0.0],
                mode=NavMode.SURFACE,
                depth_m=0.0,
                radius_m=1.0,
                speed_mps=1.0,
            ),
        )
    )
    fusion = HybridSensorFusion(pos0=[0.0, 0.0])
    patrol = PatrolExecutor(
        route,
        max_turn_rate_radps=np.pi,
        max_nav_error_m=50.0,
    )
    return HybridNavigator(fusion, patrol)


def main() -> None:
    """Run the adapter -> navigator -> command-consumer cycle."""
    navigator = build_navigator()
    adapter = DeterministicVehicleAdapter(
        pos=np.zeros(2, dtype=float),
        vel=np.zeros(2, dtype=float),
    )
    command: PatrolCommand | None = None

    for cycle in range(1, 121):
        packet = adapter.cycle(command, timestamp_s=float(cycle))
        result = navigator.step(packet)
        command = result.command

        # This is the handoff point to a supervised vehicle controller.
        if cycle == 1 or cycle % 10 == 0 or command.route_complete:
            print(
                f"cycle={cycle:03d} mode={result.state.mode.value:<9} "
                f"waypoint={command.waypoint_index} "
                f"pos=({result.state.pos[0]:5.1f}, {result.state.pos[1]:5.1f}) "
                f"depth={result.state.depth_m:4.1f} m "
                f"healthy={result.state.filter_healthy}"
            )
        if result.command.route_complete:
            break

    if not navigator.patrol.complete:
        raise RuntimeError("deterministic patrol did not complete")
    print("route_complete=True")


if __name__ == "__main__":
    main()
