"""Repeatable waypoint patrol execution for hybrid surface/submerged routes."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .fusion import HybridNavState
from .modes import NavMode


@dataclass(frozen=True)
class Waypoint:
    pos: np.ndarray
    mode: NavMode = NavMode.SURFACE
    depth_m: float = 0.0
    speed_mps: float = 1.5
    radius_m: float = 5.0
    heading_rad: float | None = None
    heading_tolerance_rad: float = np.deg2rad(20.0)
    lookahead_m: float = 12.0

    def __post_init__(self):
        p = np.asarray(self.pos, dtype=float)
        if p.shape != (2,):
            raise ValueError("waypoint pos must be a 2-vector")
        object.__setattr__(self, "pos", p)


@dataclass(frozen=True)
class PatrolRoute:
    waypoints: tuple[Waypoint, ...]
    loop: bool = False

    def __post_init__(self):
        if not self.waypoints:
            raise ValueError("patrol route needs at least one waypoint")


@dataclass(frozen=True)
class PatrolCommand:
    target_pos: np.ndarray
    desired_vel: np.ndarray
    desired_heading_rad: float
    target_depth_m: float
    target_mode: NavMode
    waypoint_index: int
    route_complete: bool = False


class PatrolExecutor:
    """Small route follower with explicit resume support."""

    def __init__(self, route: PatrolRoute,
                 max_turn_rate_radps: float = np.deg2rad(25.0),
                 low_speed_heading_mps: float = 0.15):
        self.route = route
        self.index = 0
        self.complete = False
        self.max_turn_rate_radps = float(max_turn_rate_radps)
        self.low_speed_heading_mps = float(low_speed_heading_mps)
        self._last_heading: float | None = None
        self._last_t: float | None = None

    def update(self, state: HybridNavState) -> PatrolCommand:
        wp = self.route.waypoints[self.index]
        delta = wp.pos - state.pos
        dist = float(np.linalg.norm(delta))
        desired_heading = self._bearing(delta, state.vel)
        if dist <= wp.radius_m and self._heading_ok(state, wp, desired_heading):
            self._advance()
            wp = self.route.waypoints[self.index]
            delta = self._carrot_target(state.pos, wp) - state.pos
            dist = float(np.linalg.norm(delta))
            desired_heading = self._bearing(delta, state.vel)
        else:
            delta = self._carrot_target(state.pos, wp) - state.pos
            dist = float(np.linalg.norm(delta))
            desired_heading = self._bearing(delta, state.vel)

        desired_heading = self._limit_heading(desired_heading, state.t)
        if dist > 1e-9 and not self.complete:
            desired = np.array([np.cos(desired_heading), np.sin(desired_heading)]) \
                * wp.speed_mps
        else:
            desired = np.zeros(2)

        return PatrolCommand(
            target_pos=wp.pos.copy(),
            desired_vel=desired,
            desired_heading_rad=float(desired_heading),
            target_depth_m=float(wp.depth_m),
            target_mode=wp.mode,
            waypoint_index=self.index,
            route_complete=self.complete,
        )

    def resume(self, pos: np.ndarray) -> int:
        """Resume at the nearest waypoint after surfacing/diving or restart."""
        p = np.asarray(pos, dtype=float)
        d = [float(np.linalg.norm(wp.pos - p)) for wp in self.route.waypoints]
        self.index = int(np.argmin(d))
        self.complete = False
        self._last_heading = None
        self._last_t = None
        return self.index

    def set_index(self, index: int) -> None:
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

    def _carrot_target(self, pos: np.ndarray, wp: Waypoint) -> np.ndarray:
        if self.index == 0:
            return wp.pos
        prev = self.route.waypoints[self.index - 1].pos
        seg = wp.pos - prev
        seg_len = float(np.linalg.norm(seg))
        if seg_len < 1e-9:
            return wp.pos
        u = seg / seg_len
        along = float(np.clip((pos - prev) @ u, 0.0, seg_len))
        carrot = prev + u * min(seg_len, along + max(wp.lookahead_m, wp.radius_m))
        if seg_len - along <= wp.lookahead_m and self.index + 1 < len(self.route.waypoints):
            nxt = self.route.waypoints[self.index + 1].pos
            nxt_seg = nxt - wp.pos
            nxt_len = float(np.linalg.norm(nxt_seg))
            if nxt_len > 1e-9:
                alpha = 1.0 - (seg_len - along) / max(wp.lookahead_m, 1e-9)
                next_carrot = wp.pos + nxt_seg / nxt_len * min(wp.lookahead_m, nxt_len)
                carrot = (1.0 - alpha) * carrot + alpha * next_carrot
        return carrot

    @staticmethod
    def _bearing(delta: np.ndarray, fallback_vel: np.ndarray) -> float:
        if np.linalg.norm(delta) > 1e-9:
            return float(np.arctan2(delta[1], delta[0]))
        if np.linalg.norm(fallback_vel) > 1e-9:
            return float(np.arctan2(fallback_vel[1], fallback_vel[0]))
        return 0.0

    def _heading_ok(self, state: HybridNavState, wp: Waypoint,
                    desired_heading: float) -> bool:
        target = desired_heading if wp.heading_rad is None else float(wp.heading_rad)
        if np.linalg.norm(state.vel) <= self.low_speed_heading_mps:
            return wp.heading_rad is None
        current = float(np.arctan2(state.vel[1], state.vel[0]))
        return abs(_wrap_pi(current - target)) <= wp.heading_tolerance_rad

    def _limit_heading(self, desired_heading: float, t: float) -> float:
        if self._last_heading is None or self._last_t is None:
            self._last_heading = float(desired_heading)
            self._last_t = float(t)
            return float(desired_heading)
        dt = max(float(t) - self._last_t, 0.0)
        max_delta = self.max_turn_rate_radps * dt
        delta = _wrap_pi(float(desired_heading) - self._last_heading)
        if max_delta > 0.0:
            delta = float(np.clip(delta, -max_delta, max_delta))
        limited = _wrap_pi(self._last_heading + delta)
        self._last_heading = limited
        self._last_t = float(t)
        return limited


def _wrap_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)
