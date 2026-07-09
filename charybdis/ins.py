"""Strapdown inertial navigation (2-D horizontal dead-reckoning).

Integrates measured specific force in the nav frame to propagate position and
velocity. With no aiding this drifts without bound; it is the baseline the
terrain-aided EKF must beat.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class InsState:
    pos: np.ndarray          # [2]
    vel: np.ndarray          # [2]


class StrapdownINS:
    def __init__(self, pos0, vel0):
        self.state = InsState(pos=np.asarray(pos0, float).copy(),
                              vel=np.asarray(vel0, float).copy())

    def propagate(self, accel: np.ndarray, dt: float) -> InsState:
        s = self.state
        accel = np.asarray(accel, float)
        s.pos = s.pos + s.vel * dt + 0.5 * accel * dt * dt
        s.vel = s.vel + accel * dt
        return s

    @property
    def pos(self) -> np.ndarray:
        return self.state.pos

    @property
    def vel(self) -> np.ndarray:
        return self.state.vel
