"""Recommended adapter -> navigator -> command handoff pattern.

The classes below stand in for drivers, policy, and a controller boundary. A
real vehicle integration would replace them while keeping `HybridNavigator.step`
as the navigation/guidance boundary.
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
class SensorAdapter:
    """Convert synchronized driver values into one coherent sensor packet."""

    pos: np.ndarray
    vel: np.ndarray
    depth_m: float = 0.0
    dt: float = 1.0

    def read_packet(
        self,
        previous_command: PatrolCommand | None,
        *,
        timestamp_s: float,
    ) -> SensorPacket:
        previous_vel = self.vel.copy()
        if previous_command is not None:
            self.vel = previous_command.desired_vel.copy()
            self.pos += self.vel * self.dt
            depth_error = previous_command.target_depth_m - self.depth_m
            self.depth_m += float(np.clip(depth_error, -0.75, 0.75))

        accel = (self.vel - previous_vel) / self.dt
        surfaced = self.depth_m <= 1.5
        gps = (
            GpsMeasurement(
                self.pos,
                self.vel,
                pos_cov=np.diag([1.0, 1.0]) ** 2,
                vel_cov=np.diag([0.08, 0.08]) ** 2,
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
                cov=np.diag([0.08, 0.08]) ** 2,
                timestamp_s=timestamp_s,
            )
        )
        return SensorPacket(
            imu=ImuMeasurement(accel, self.dt, timestamp_s=timestamp_s),
            gps=gps,
            depth=DepthMeasurement(self.depth_m, timestamp_s=timestamp_s),
            velocity=velocity,
            mode_hint=None
            if previous_command is None
            else previous_command.target_mode,
            timestamp_s=timestamp_s,
        )


class HealthPolicy:
    """Example handoff policy between library guidance and vehicle control."""

    def allow_handoff(self, command: PatrolCommand, *, healthy: bool) -> bool:
        return healthy and not command.route_complete


class CommandSink:
    """Placeholder for a supervised vehicle controller."""

    def __init__(self) -> None:
        self.last_command: PatrolCommand | None = None

    def send(self, command: PatrolCommand) -> None:
        self.last_command = command


def build_navigator() -> HybridNavigator:
    route = PatrolRoute(
        (
            Waypoint([8.0, 0.0], mode=NavMode.SURFACE, radius_m=2.0),
            Waypoint([18.0, 0.0], mode=NavMode.SUBMERGED, depth_m=5.0, radius_m=4.0),
            Waypoint([24.0, 0.0], mode=NavMode.SURFACE, depth_m=0.0, radius_m=3.0),
        )
    )
    return HybridNavigator(
        HybridSensorFusion(pos0=[0.0, 0.0]),
        PatrolExecutor(route, max_nav_error_m=75.0),
    )


def main() -> None:
    navigator = build_navigator()
    adapter = SensorAdapter(pos=np.zeros(2), vel=np.zeros(2))
    policy = HealthPolicy()
    sink = CommandSink()
    command: PatrolCommand | None = None

    for step in range(1, 61):
        packet = adapter.read_packet(command, timestamp_s=float(step))
        result = navigator.step(packet)
        if policy.allow_handoff(result.command, healthy=result.state.filter_healthy):
            sink.send(result.command)
            command = sink.last_command
        else:
            command = None
        if result.command.route_complete:
            break

    if sink.last_command is None:
        raise RuntimeError("adapter pattern did not produce a command handoff")
    print(f"handoff_healthy={result.state.filter_healthy}")
    print(f"final_mode={result.state.mode.value}")
    print(f"last_waypoint={sink.last_command.waypoint_index}")


if __name__ == "__main__":
    main()
