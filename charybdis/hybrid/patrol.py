"""Repeatable waypoint patrol execution for hybrid surface/submerged routes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .fusion import HybridNavState
from .modes import NavMode

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class Waypoint:
    """One horizontal route target with optional mode, depth, and heading."""

    pos: ArrayLike
    mode: NavMode = NavMode.SURFACE
    depth_m: float = 0.0
    speed_mps: float = 1.5
    radius_m: float = 5.0
    heading_rad: float | None = None
    heading_tolerance_rad: float = np.deg2rad(20.0)
    lookahead_m: float = 12.0
    depth_tolerance_m: float = 0.75

    def __post_init__(self) -> None:
        p = np.array(self.pos, dtype=np.float64, copy=True)
        if p.shape != (2,) or not np.all(np.isfinite(p)):
            raise ValueError("waypoint pos must be a finite 2-vector")
        scalars = {
            "depth_m": self.depth_m,
            "speed_mps": self.speed_mps,
            "radius_m": self.radius_m,
            "heading_tolerance_rad": self.heading_tolerance_rad,
            "lookahead_m": self.lookahead_m,
            "depth_tolerance_m": self.depth_tolerance_m,
        }
        if any(not np.isfinite(value) for value in scalars.values()):
            raise ValueError("waypoint guidance values must be finite")
        if (
            self.depth_m < 0.0
            or self.speed_mps < 0.0
            or self.lookahead_m < 0.0
            or self.depth_tolerance_m < 0.0
        ):
            raise ValueError(
                "depth, speed, lookahead, and depth tolerance must be non-negative"
            )
        if self.radius_m <= 0.0:
            raise ValueError("radius_m must be positive")
        if not 0.0 < self.heading_tolerance_rad <= np.pi:
            raise ValueError("heading_tolerance_rad must be in (0, pi]")
        heading = self.heading_rad
        if heading is not None:
            if not np.isfinite(heading):
                raise ValueError("heading_rad must be finite")
            object.__setattr__(self, "heading_rad", _wrap_pi(float(heading)))
        p.setflags(write=False)
        object.__setattr__(self, "pos", p)
        object.__setattr__(self, "mode", NavMode(self.mode))


@dataclass(frozen=True)
class PatrolRoute:
    """Ordered waypoint route that may optionally repeat."""

    waypoints: tuple[Waypoint, ...]
    loop: bool = False

    def __post_init__(self) -> None:
        waypoints = tuple(self.waypoints)
        if not waypoints:
            raise ValueError("patrol route needs at least one waypoint")
        if not all(isinstance(waypoint, Waypoint) for waypoint in waypoints):
            raise TypeError("waypoints must contain Waypoint instances")
        if not isinstance(self.loop, bool):
            raise TypeError("loop must be bool")
        object.__setattr__(self, "waypoints", waypoints)


@dataclass(frozen=True)
class PatrolCommand:
    """Guidance command generated for the current patrol target."""

    target_pos: FloatArray
    desired_vel: FloatArray
    desired_heading_rad: float
    target_depth_m: float
    target_mode: NavMode
    waypoint_index: int
    route_complete: bool = False

    def __post_init__(self) -> None:
        target = np.array(self.target_pos, dtype=np.float64, copy=True)
        velocity = np.array(self.desired_vel, dtype=np.float64, copy=True)
        if (
            target.shape != (2,)
            or velocity.shape != (2,)
            or not np.all(np.isfinite(target))
            or not np.all(np.isfinite(velocity))
        ):
            raise ValueError("command vectors must be finite 2-vectors")
        if (
            not np.isfinite(self.desired_heading_rad)
            or not np.isfinite(self.target_depth_m)
            or self.target_depth_m < 0.0
            or self.waypoint_index < 0
        ):
            raise ValueError("command scalar values are invalid")
        target.setflags(write=False)
        velocity.setflags(write=False)
        object.__setattr__(self, "target_pos", target)
        object.__setattr__(self, "desired_vel", velocity)
        object.__setattr__(
            self, "desired_heading_rad", _wrap_pi(self.desired_heading_rad)
        )
        object.__setattr__(self, "target_mode", NavMode(self.target_mode))


class PatrolExecutor:
    """Heading-aware LOS route follower with explicit resume support.

    A carrot target smooths segment tracking and blends toward the next segment
    near a waypoint. Desired heading changes are bounded by
    ``max_turn_rate_radps``.
    """

    def __init__(
        self,
        route: PatrolRoute,
        max_turn_rate_radps: float = np.deg2rad(25.0),
        low_speed_heading_mps: float = 0.15,
        max_nav_error_m: float = 100.0,
    ) -> None:
        """Initialize guidance for a route and its turn-rate constraint."""
        values = (max_turn_rate_radps, low_speed_heading_mps, max_nav_error_m)
        if not all(np.isfinite(value) for value in values):
            raise ValueError("patrol limits must be finite")
        if max_turn_rate_radps < 0.0 or low_speed_heading_mps < 0.0:
            raise ValueError("turn rate and low-speed threshold must be non-negative")
        if max_nav_error_m <= 0.0:
            raise ValueError("max_nav_error_m must be positive")
        self.route = route
        self.index = 0
        self.complete = False
        self.max_turn_rate_radps = float(max_turn_rate_radps)
        self.low_speed_heading_mps = float(low_speed_heading_mps)
        self.max_nav_error_m = float(max_nav_error_m)
        self._last_heading: float | None = None
        self._last_t: float | None = None

    def update(self, state: HybridNavState) -> PatrolCommand:
        """Advance waypoint state as needed and produce the next command."""
        wp = self.route.waypoints[self.index]
        wp_pos = cast(FloatArray, wp.pos)
        delta = wp_pos - state.pos
        dist = float(np.linalg.norm(delta))
        desired_heading = self._bearing(delta, state.vel)
        if dist <= wp.radius_m and self._arrival_ok(state, wp):
            self._advance()
            wp = self.route.waypoints[self.index]
            wp_pos = cast(FloatArray, wp.pos)
            delta = self._carrot_target(state.pos, wp) - state.pos
            dist = float(np.linalg.norm(delta))
            desired_heading = self._bearing(delta, state.vel)
        else:
            delta = self._carrot_target(state.pos, wp) - state.pos
            dist = float(np.linalg.norm(delta))
            desired_heading = self._bearing(delta, state.vel)

        desired_heading = self._limit_heading(desired_heading, state.t)
        nav_safe = state.filter_healthy and (
            state.error_radius_1sigma <= self.max_nav_error_m
        )
        if dist > 1e-9 and not self.complete and nav_safe:
            desired = (
                np.array([np.cos(desired_heading), np.sin(desired_heading)])
                * wp.speed_mps
            )
        else:
            desired = np.zeros(2)

        return PatrolCommand(
            target_pos=wp_pos.copy(),
            desired_vel=desired,
            desired_heading_rad=float(desired_heading),
            target_depth_m=float(wp.depth_m),
            target_mode=wp.mode,
            waypoint_index=self.index,
            route_complete=self.complete,
        )

    def resume(self, pos: ArrayLike) -> int:
        """Resume at the nearest waypoint after surfacing/diving or restart."""
        p = np.asarray(pos, dtype=float)
        d = [
            float(np.linalg.norm(cast(FloatArray, wp.pos) - p))
            for wp in self.route.waypoints
        ]
        self.index = int(np.argmin(d))
        self.complete = False
        self._last_heading = None
        self._last_t = None
        return self.index

    def set_index(self, index: int) -> None:
        """Resume explicitly at a route index."""
        if not 0 <= index < len(self.route.waypoints):
            raise IndexError(index)
        self.index = int(index)
        self.complete = False
        self._last_heading = None
        self._last_t = None

    def _advance(self) -> None:
        if self.complete:
            return
        nxt = self.index + 1
        if nxt < len(self.route.waypoints):
            self.index = nxt
        elif self.route.loop:
            self.index = 0
        else:
            self.complete = True
        self._last_heading = None
        self._last_t = None

    def _carrot_target(self, pos: FloatArray, wp: Waypoint) -> FloatArray:
        wp_pos = cast(FloatArray, wp.pos)
        if self.index == 0 and not self.route.loop:
            return wp_pos
        previous_pos = (
            self.route.waypoints[-1].pos
            if self.index == 0
            else self.route.waypoints[self.index - 1].pos
        )
        prev = cast(FloatArray, previous_pos)
        seg = wp_pos - prev
        seg_len = float(np.linalg.norm(seg))
        if seg_len < 1e-9:
            return wp_pos
        u = seg / seg_len
        along = float(np.clip((pos - prev) @ u, 0.0, seg_len))
        carrot = prev + u * min(seg_len, along + max(wp.lookahead_m, wp.radius_m))
        if seg_len - along <= wp.lookahead_m and self.index + 1 < len(
            self.route.waypoints
        ):
            nxt = cast(FloatArray, self.route.waypoints[self.index + 1].pos)
            nxt_seg = nxt - wp_pos
            nxt_len = float(np.linalg.norm(nxt_seg))
            if nxt_len > 1e-9:
                alpha = float(
                    np.clip(
                        1.0 - (seg_len - along) / max(wp.lookahead_m, 1e-9),
                        0.0,
                        1.0,
                    )
                )
                next_carrot = wp_pos + nxt_seg / nxt_len * min(wp.lookahead_m, nxt_len)
                carrot = (1.0 - alpha) * carrot + alpha * next_carrot
        return carrot

    @staticmethod
    def _bearing(delta: FloatArray, fallback_vel: FloatArray) -> float:
        if np.linalg.norm(delta) > 1e-9:
            return float(np.arctan2(delta[1], delta[0]))
        if np.linalg.norm(fallback_vel) > 1e-9:
            return float(np.arctan2(fallback_vel[1], fallback_vel[0]))
        return 0.0

    def _heading_ok(self, state: HybridNavState, wp: Waypoint) -> bool:
        if wp.heading_rad is None:
            return True
        target = float(wp.heading_rad)
        if np.linalg.norm(state.vel) <= self.low_speed_heading_mps:
            return False
        current = float(np.arctan2(state.vel[1], state.vel[0]))
        return abs(_wrap_pi(current - target)) <= wp.heading_tolerance_rad

    def _arrival_ok(self, state: HybridNavState, wp: Waypoint) -> bool:
        mode_and_depth_ok = (
            state.mode == wp.mode
            and abs(state.depth_m - wp.depth_m) <= wp.depth_tolerance_m
        )
        return mode_and_depth_ok and self._heading_ok(state, wp)

    def _limit_heading(self, desired_heading: float, t: float) -> float:
        if self._last_heading is None or self._last_t is None:
            self._last_heading = float(desired_heading)
            self._last_t = float(t)
            return float(desired_heading)
        dt = float(t) - self._last_t
        if dt <= 0.0:
            return float(self._last_heading)
        max_delta = self.max_turn_rate_radps * dt
        delta = _wrap_pi(float(desired_heading) - self._last_heading)
        delta = float(np.clip(delta, -max_delta, max_delta))
        limited = _wrap_pi(self._last_heading + delta)
        self._last_heading = limited
        self._last_t = float(t)
        return limited


def _wrap_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)
