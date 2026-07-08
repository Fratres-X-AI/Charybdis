"""Online terrain SLAM for Charybdis UUV navigation. [Experimental]

See docs/MATURITY.md. Maintains a growing pose graph with local bathymetric
submaps. Loop closures are detected by correlating a live submap against prior
submaps; pose nodes are refined with sparse nonlinear least squares (scipy).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np
from scipy.optimize import least_squares


@dataclass
class Submap:
    anchor: np.ndarray          # pose when submap started [x, y]
    depths: list = field(default_factory=list)   # (rel_xy, depth) samples
    pose_idx: int = 0


@dataclass
class SlamState:
    poses: list = field(default_factory=list)    # [x, y] estimates
    submaps: list = field(default_factory=list)
    edges: list = field(default_factory=list)      # (i, j, meas_ij)
    current: np.ndarray = field(default_factory=lambda: np.zeros(2))
    step_count: int = 0


def init_slam(start: np.ndarray | None = None) -> SlamState:
    s = SlamState()
    p = np.asarray(start if start is not None else (0.0, 0.0), float).copy()
    s.poses.append(p.copy()); s.current = p.copy()
    s.submaps.append(Submap(anchor=p.copy(), pose_idx=0))
    return s


def predict(s: SlamState, velocity: np.ndarray, dt: float = 1.0) -> None:
    s.current = s.current + np.asarray(velocity, float) * dt
    s.poses.append(s.current.copy())
    s.step_count += 1
    if s.step_count % 12 == 0:
        s.submaps.append(Submap(anchor=s.current.copy(), pose_idx=len(s.poses) - 1))


def ingest_scan(s: SlamState, rel_xy: np.ndarray, depth: float) -> None:
    s.submaps[-1].depths.append((np.asarray(rel_xy, float).copy(), float(depth)))


def _submap_vector(sm: Submap, bathy, n: int = 16, span: float = 5.0) -> np.ndarray:
    axis = np.linspace(-span, span, n)
    gx, gy = np.meshgrid(axis, axis)
    z = bathy(sm.anchor[0] + gx, sm.anchor[1] + gy)
    z = z - z.mean()
    return z.ravel()


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a) + 1e-9
    nb = np.linalg.norm(b) + 1e-9
    return float(np.dot(a, b) / (na * nb))


def detect_loop(s: SlamState, bathy, min_corr: float = 0.82) -> tuple[int, int, np.ndarray] | None:
    if len(s.submaps) < 2:
        return None
    cur = s.submaps[-1]
    v_cur = _submap_vector(cur, bathy)
    best = None
    for old in s.submaps[:-2]:
        r = _corr(v_cur, _submap_vector(old, bathy))
        if r >= min_corr and (best is None or r > best[0]):
            best = (r, old.pose_idx, cur.pose_idx, cur.anchor - old.anchor)
    if best is None:
        return None
    return best[1], best[2], best[3]


def add_odometry_edge(s: SlamState, i: int, j: int, meas: np.ndarray) -> None:
    s.edges.append((i, j, np.asarray(meas, float).copy()))


def optimize(s: SlamState, max_iter: int = 40) -> None:
    if len(s.poses) < 2:
        return
    x0 = np.array(s.poses, float).ravel()
    edges = s.edges[-max(0, len(s.poses) - 1):]  # recent chain + loops

    def residual(vec):
        P = vec.reshape(-1, 2)
        rs = []
        for i, j, m in edges:
            rs.extend(P[j] - P[i] - m)
        rs.append(0.01 * (P[0, 0] - s.poses[0][0]))
        rs.append(0.01 * (P[0, 1] - s.poses[0][1]))
        return np.array(rs, float)

    res = least_squares(residual, x0, max_nfev=max_iter * len(x0))
    s.poses = [p.copy() for p in res.x.reshape(-1, 2)]
    s.current = s.poses[-1].copy()


def slam_step(s: SlamState, velocity: np.ndarray, bathy, dt: float = 1.0) -> bool:
    """One SLAM tick; returns True if a loop closure was added."""
    prev = len(s.poses) - 1
    predict(s, velocity, dt)
    j = len(s.poses) - 1
    add_odometry_edge(s, prev, j, velocity * dt)
    loop = detect_loop(s, bathy)
    if loop is not None:
        i, j, meas = loop
        add_odometry_edge(s, i, j, meas)
        optimize(s)
        return True
    return False


def position_error(s: SlamState, true_pos: np.ndarray) -> float:
    return float(np.hypot(*(s.current - true_pos)))
