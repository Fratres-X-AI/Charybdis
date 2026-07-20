"""Minimal 4DOF UUV plant closed around patrol guidance commands."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .frames import wrap_pi
from .patrol import PatrolCommand

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class VehiclePlantConfig:
    """First-order surge/heading/depth response around guidance setpoints."""

    surge_tau_s: float = 6.0
    heading_rate_max_radps: float = np.deg2rad(25.0)
    depth_tau_s: float = 8.0
    current_xy_mps: tuple[float, float] = (0.0, 0.0)
    max_surge_mps: float = 2.5

    def __post_init__(self) -> None:
        positive = (
            "surge_tau_s",
            "heading_rate_max_radps",
            "depth_tau_s",
            "max_surge_mps",
        )
        for name in positive:
            value = float(getattr(self, name))
            if not np.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        current = tuple(float(value) for value in self.current_xy_mps)
        if len(current) != 2 or not np.all(np.isfinite(current)):
            raise ValueError("current_xy_mps must contain two finite values")
        object.__setattr__(self, "current_xy_mps", current)


@dataclass
class VehicleState:
    """Ground-truth 4DOF vehicle state in the local ENU navigation frame."""

    pos: FloatArray
    vel: FloatArray
    heading_rad: float
    depth_m: float

    def __post_init__(self) -> None:
        pos = np.asarray(self.pos, dtype=np.float64, copy=True)
        vel = np.asarray(self.vel, dtype=np.float64, copy=True)
        if pos.shape != (2,) or vel.shape != (2,):
            raise ValueError("pos and vel must be 2-vectors")
        if not np.all(np.isfinite(pos)) or not np.all(np.isfinite(vel)):
            raise ValueError("pos and vel must be finite")
        heading = wrap_pi(float(self.heading_rad))
        depth = float(self.depth_m)
        if not np.isfinite(depth) or depth < 0.0:
            raise ValueError("depth_m must be finite and non-negative")
        self.pos = pos
        self.vel = vel
        self.heading_rad = heading
        self.depth_m = depth

    @property
    def speed_mps(self) -> float:
        """Horizontal speed over ground including current."""
        return float(np.linalg.norm(self.vel))


class VehiclePlant:
    """Propagate surge, heading, and depth toward ``PatrolCommand`` setpoints."""

    def __init__(
        self, state: VehicleState, cfg: VehiclePlantConfig | None = None
    ) -> None:
        if not isinstance(state, VehicleState):
            raise TypeError("state must be VehicleState")
        self.state = state
        self.cfg = cfg or VehiclePlantConfig()

    def step(self, command: PatrolCommand, dt: float) -> VehicleState:
        """Advance the plant one interval and return the updated state."""
        step = float(dt)
        if not np.isfinite(step) or step <= 0.0:
            raise ValueError("dt must be finite and positive")
        if not isinstance(command, PatrolCommand):
            raise TypeError("command must be PatrolCommand")

        desired_heading = wrap_pi(float(command.desired_heading_rad))
        heading_error = wrap_pi(desired_heading - self.state.heading_rad)
        max_turn = self.cfg.heading_rate_max_radps * step
        heading_delta = float(np.clip(heading_error, -max_turn, max_turn))
        next_heading = wrap_pi(self.state.heading_rad + heading_delta)

        desired_surge = float(np.linalg.norm(command.desired_vel))
        desired_surge = min(desired_surge, self.cfg.max_surge_mps)
        surge_alpha = min(step / max(self.cfg.surge_tau_s, step), 1.0)
        current_speed = float(
            np.linalg.norm(
                self.state.vel - np.asarray(self.cfg.current_xy_mps, dtype=float)
            )
        )
        next_speed = current_speed + (desired_surge - current_speed) * surge_alpha
        body_vel = np.array([next_speed, 0.0], dtype=np.float64)
        nav_vel = np.array(
            [
                np.cos(next_heading) * body_vel[0],
                np.sin(next_heading) * body_vel[0],
            ],
            dtype=np.float64,
        ) + np.asarray(self.cfg.current_xy_mps, dtype=float)

        depth_alpha = min(step / max(self.cfg.depth_tau_s, step), 1.0)
        next_depth = (
            self.state.depth_m
            + (float(command.target_depth_m) - self.state.depth_m) * depth_alpha
        )
        next_depth = max(float(next_depth), 0.0)
        next_pos = self.state.pos + nav_vel * step

        self.state = VehicleState(
            pos=next_pos,
            vel=nav_vel,
            heading_rad=next_heading,
            depth_m=next_depth,
        )
        return self.state


__all__ = ["VehiclePlant", "VehiclePlantConfig", "VehicleState"]
