"""Bathymetric SLAM for Charybdis: submap GICP + pose-graph optimization.

WARNING: Experimental / unstable API. Do not use in production navigation
paths. Import through :mod:`charybdis.experimental`.

Maintains local elevation submaps, detects loop closures via GICP alignment
(Generalized ICP on gradient-weighted point clouds), and refines poses with
sparse nonlinear least squares.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import least_squares

from ..terrain import Terrain


@dataclass
class Submap:
    anchor: np.ndarray
    pose_idx: int = 0
    grid: np.ndarray | None = None
    step: float = 25.0


@dataclass
class SlamState:
    poses: list = field(default_factory=list)
    submaps: list = field(default_factory=list)
    edges: list = field(default_factory=list)
    current: np.ndarray = field(default_factory=lambda: np.zeros(2))
    step_count: int = 0


def init_slam(start: np.ndarray | None = None) -> SlamState:
    s = SlamState()
    p = np.asarray(start if start is not None else (0.0, 0.0), float).copy()
    s.poses.append(p.copy())
    s.current = p.copy()
    s.submaps.append(Submap(anchor=p.copy(), pose_idx=0))
    return s


def _submap_grid(sm: Submap, terrain: Terrain, n: int = 16,
                 span: float = 400.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    axis = np.linspace(-span, span, n)
    gx, gy = np.meshgrid(axis, axis)
    wx = sm.anchor[0] + gx
    wy = sm.anchor[1] + gy
    z = terrain.elevation(wx, wy)
    z = z - z.mean()
    pts = np.stack([gx.ravel(), gy.ravel(), z.ravel()], axis=1)
    return pts, gx, gy


def _gicp_step(src: np.ndarray, dst: np.ndarray, t: np.ndarray) -> tuple[np.ndarray, float]:
    """One ICP iteration with elevation-gradient weights (GICP-lite)."""
    moved = src[:, :2] + t
    diff = moved[:, None, :] - dst[None, :, :2]
    d2 = np.sum(diff * diff, axis=2)
    j = np.argmin(d2, axis=1)
    matched = dst[j]
    w = np.abs(matched[:, 2]) + 0.1
    w /= w.sum() + 1e-9
    delta = matched[:, :2] - moved
    dt = np.sum(delta * w[:, None], axis=0)
    err = float(np.sum(w * np.sum(delta * delta, axis=1)))
    return t + dt, err


def gicp_align(src_pts: np.ndarray, dst_pts: np.ndarray,
               init: np.ndarray | None = None, iters: int = 12) -> tuple[np.ndarray, float]:
    """Align src to dst; return translation [dx, dy] and final error."""
    t = np.zeros(2) if init is None else np.asarray(init, float).copy()
    err = 1e9
    for _ in range(iters):
        t, err = _gicp_step(src_pts, dst_pts, t)
    return t, err


def build_submap(sm: Submap, terrain: Terrain) -> None:
    pts, _, _ = _submap_grid(sm, terrain)
    sm.grid = pts


def predict(s: SlamState, velocity: np.ndarray, dt: float = 1.0) -> None:
    s.current = s.current + np.asarray(velocity, float) * dt
    s.poses.append(s.current.copy())
    s.step_count += 1
    if s.step_count % 12 == 0:
        s.submaps.append(Submap(anchor=s.current.copy(), pose_idx=len(s.poses) - 1))


def add_edge(s: SlamState, i: int, j: int, meas: np.ndarray,
             info: float = 1.0) -> None:
    s.edges.append((i, j, np.asarray(meas, float).copy(), float(info)))


def detect_loop_gicp(s: SlamState, terrain: Terrain,
                     min_err: float = 80.0) -> tuple[int, int, np.ndarray] | None:
    if len(s.submaps) < 2:
        return None
    cur = s.submaps[-1]
    build_submap(cur, terrain)
    best = None
    for old in s.submaps[:-2]:
        build_submap(old, terrain)
        t, err = gicp_align(cur.grid, old.grid)
        if err <= min_err and (best is None or err < best[0]):
            meas = cur.anchor - old.anchor + t
            best = (err, old.pose_idx, cur.pose_idx, meas)
    if best is None:
        return None
    return best[1], best[2], best[3]


def optimize(s: SlamState, max_iter: int = 40) -> None:
    if len(s.poses) < 2:
        return
    x0 = np.array(s.poses, float).ravel()
    edges = s.edges

    def residual(vec):
        P = vec.reshape(-1, 2)
        rs = []
        for i, j, m, w in edges:
            e = P[j] - P[i] - m
            rs.extend(np.sqrt(w) * e)
        rs.append(0.01 * (P[0, 0] - s.poses[0][0]))
        rs.append(0.01 * (P[0, 1] - s.poses[0][1]))
        return np.array(rs, float)

    res = least_squares(residual, x0, max_nfev=max_iter * len(x0))
    s.poses = [p.copy() for p in res.x.reshape(-1, 2)]
    s.current = s.poses[-1].copy()


def slam_step(s: SlamState, velocity: np.ndarray, terrain: Terrain,
              dt: float = 1.0) -> bool:
    prev = len(s.poses) - 1
    predict(s, velocity, dt)
    j = len(s.poses) - 1
    add_edge(s, prev, j, velocity * dt, info=1.0)
    loop = detect_loop_gicp(s, terrain)
    if loop is not None:
        i, j, meas = loop
        add_edge(s, i, j, meas, info=4.0)
        optimize(s)
        return True
    return False


def position_error(s: SlamState, true_pos: np.ndarray) -> float:
    return float(np.linalg.norm(s.current - true_pos))
