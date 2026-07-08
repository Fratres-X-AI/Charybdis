"""Multi-contact tracking for Charybdis.

While the UUV navigates, its passive sonar detects other contacts (surface
traffic, submerged units). Each contact is tracked by an independent
constant-velocity Kalman filter fed noisy range/bearing measurements taken from
the ownship's *believed* position - so tracking accuracy degrades gracefully as
the nav solution drifts, which is exactly the operational coupling we want to
show on the tactical picture.

Runs on its own RNG stream so it never perturbs the seeded nav-sensor noise.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np

_F = None
_H = np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]])


def _transition(dt: float) -> np.ndarray:
    return np.array([[1, 0, dt, 0], [0, 1, 0, dt], [0, 0, 1, 0], [0, 0, 0, 1]],
                    dtype=float)


@dataclass
class Contact:
    cid: str
    kind: str                       # "SURFACE" | "SUBSURFACE"
    state: np.ndarray               # true [x, y, vx, vy]
    est: np.ndarray                 # tracked [x, y, vx, vy]
    P: np.ndarray
    detected: bool = True
    range_m: float = 0.0
    bearing_deg: float = 0.0


@dataclass
class TrackingWorld:
    contacts: list = field(default_factory=list)
    meas_noise: float = 1.5         # range/bearing derived position noise [m]
    proc_noise: float = 0.03        # contact manoeuvre noise
    detect_range: float = 90.0      # passive detection horizon [m]


def spawn(n: int, rng: np.random.Generator,
          bounds=(0.0, 120.0)) -> TrackingWorld:
    """Create ``n`` contacts with random pose/velocity inside the op area."""
    w = TrackingWorld()
    lo, hi = bounds
    for i in range(n):
        pos = rng.uniform(lo, hi, size=2)
        vel = rng.normal(0.0, 0.6, size=2)
        kind = "SURFACE" if rng.random() < 0.5 else "SUBSURFACE"
        st = np.concatenate([pos, vel])
        w.contacts.append(Contact(
            cid=f"C{i + 1:02d}", kind=kind, state=st.copy(),
            est=st + np.concatenate([rng.normal(0, 3, 2), np.zeros(2)]),
            P=np.diag([9.0, 9.0, 1.0, 1.0])))
    return w


def step(w: TrackingWorld, ownship_pos: np.ndarray, dt: float,
         rng: np.random.Generator) -> None:
    """Advance true contacts and update each track (predict + gated update)."""
    F = _transition(dt)
    Q = np.diag([0.0, 0.0, w.proc_noise ** 2, w.proc_noise ** 2])
    R = np.eye(2) * w.meas_noise ** 2

    for c in w.contacts:
        # --- true contact motion (constant velocity + manoeuvre noise) ----- #
        c.state = F @ c.state
        c.state[2:] += rng.normal(0.0, w.proc_noise, size=2)

        rel = c.state[:2] - ownship_pos
        rng_true = float(np.hypot(*rel))
        c.range_m = rng_true
        c.bearing_deg = float(np.degrees(np.arctan2(rel[0], rel[1])) % 360.0)
        c.detected = rng_true <= w.detect_range

        # --- track predict ------------------------------------------------- #
        c.est = F @ c.est
        c.P = F @ c.P @ F.T + Q

        if not c.detected:
            continue

        # --- track update from noisy position measurement ------------------ #
        z = c.state[:2] + rng.normal(0.0, w.meas_noise, size=2)
        y = z - _H @ c.est
        S = _H @ c.P @ _H.T + R
        K = c.P @ _H.T @ np.linalg.inv(S)
        c.est = c.est + K @ y
        c.P = (np.eye(4) - K @ _H) @ c.P


def track_error(w: TrackingWorld) -> float:
    """Mean position error over currently detected tracks [m]."""
    errs = [float(np.hypot(*(c.est[:2] - c.state[:2])))
            for c in w.contacts if c.detected]
    return float(np.mean(errs)) if errs else 0.0
