"""Regression tests for GPS-denied patrol waypoint handoffs."""

from __future__ import annotations

import numpy as np
from charybdis.hybrid import HybridNavState, NavMode
from charybdis.hybrid.patrol import PatrolExecutor, PatrolRoute, Waypoint


def _state(
    pos: list[float],
    *,
    depth_m: float = 0.0,
    mode: NavMode = NavMode.SURFACE,
    vel: list[float] | None = None,
    t: float = 0.0,
) -> HybridNavState:
    return HybridNavState(
        np.asarray(pos, dtype=float),
        np.asarray(vel or [1.0, 0.0], dtype=float),
        np.eye(8),
        mode,
        depth_m=depth_m,
        t=t,
    )


def test_submerged_wp_advances_when_next_is_surface_sniff_despite_depth_lag():
    """Horizontal arrival at a submerged leg must not block the surface GPS sniff."""
    route = PatrolRoute(
        (
            Waypoint([0.0, 0.0], mode=NavMode.SURFACE, radius_m=5.0),
            Waypoint(
                [100.0, 0.0],
                mode=NavMode.SUBMERGED,
                depth_m=200.0,
                radius_m=12.0,
                depth_tolerance_m=5.0,
            ),
            Waypoint(
                [120.0, 0.0],
                mode=NavMode.SURFACE,
                depth_m=0.0,
                radius_m=10.0,
                depth_tolerance_m=1.0,
            ),
        )
    )
    patrol = PatrolExecutor(route)
    patrol.set_index(1)

    # Overshot horizontally while still diving — must hand off to surface sniff.
    cmd = patrol.update(
        _state([112.0, 0.0], depth_m=80.0, mode=NavMode.SUBMERGED, t=1.0)
    )
    assert cmd.waypoint_index == 2
    assert cmd.target_mode == NavMode.SURFACE


def test_intermediate_surface_wp_allows_depth_mismatch():
    """GPS sniff / transit surface legs are not terminal depth holds."""
    route = PatrolRoute(
        (
            Waypoint([0.0, 0.0], mode=NavMode.SURFACE, radius_m=5.0),
            Waypoint(
                [50.0, 0.0],
                mode=NavMode.SURFACE,
                depth_m=0.0,
                radius_m=8.0,
                depth_tolerance_m=1.0,
            ),
            Waypoint(
                [100.0, 0.0],
                mode=NavMode.SUBMERGED,
                depth_m=120.0,
                radius_m=10.0,
            ),
        )
    )
    patrol = PatrolExecutor(route)
    patrol.set_index(1)

    cmd = patrol.update(
        _state([50.0, 0.0], depth_m=6.0, mode=NavMode.SURFACE, t=1.0)
    )
    assert cmd.waypoint_index == 2


def test_terminal_submerged_wp_still_requires_depth_convergence():
    route = PatrolRoute(
        (
            Waypoint([0.0, 0.0], mode=NavMode.SURFACE, radius_m=5.0),
            Waypoint(
                [80.0, 0.0],
                mode=NavMode.SUBMERGED,
                depth_m=200.0,
                radius_m=10.0,
                depth_tolerance_m=5.0,
            ),
        )
    )
    patrol = PatrolExecutor(route)
    patrol.set_index(1)

    stuck = patrol.update(
        _state([80.0, 0.0], depth_m=40.0, mode=NavMode.SUBMERGED, t=1.0)
    )
    assert stuck.waypoint_index == 1

    advanced = patrol.update(
        _state([80.0, 0.0], depth_m=198.0, mode=NavMode.SUBMERGED, t=2.0)
    )
    assert advanced.route_complete


def test_along_track_passed_waypoint_detects_overshoot():
    route = PatrolRoute(
        (
            Waypoint([0.0, 0.0], mode=NavMode.SURFACE, radius_m=5.0),
            Waypoint(
                [100.0, 0.0],
                mode=NavMode.SUBMERGED,
                depth_m=150.0,
                radius_m=15.0,
                depth_tolerance_m=5.0,
            ),
            Waypoint(
                [130.0, 0.0],
                mode=NavMode.SURFACE,
                radius_m=12.0,
            ),
        )
    )
    patrol = PatrolExecutor(route)
    patrol.set_index(1)

    # Past the submerged waypoint along-track, outside capture radius.
    cmd = patrol.update(
        _state([118.0, 0.0], depth_m=60.0, mode=NavMode.SUBMERGED, t=1.0)
    )
    assert cmd.waypoint_index == 2
