"""Truth trajectory generation for the interceptor.

Produces a smooth, banking flight path (position, velocity, specific force,
heading) over the terrain. This is ground-truth only; the navigator never
sees it directly.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .config import SimConfig
from .terrain import Terrain


@dataclass
class Trajectory:
    t: np.ndarray            # [N]
    pos: np.ndarray          # [N, 2] ENU x, y  [m]
    vel: np.ndarray          # [N, 2] [m/s]
    acc: np.ndarray          # [N, 2] specific force in nav frame [m/s^2]
    heading: np.ndarray      # [N] rad
    alt_msl: np.ndarray      # [N] altitude above sea level [m]

    def __len__(self) -> int:
        return self.t.size


def generate_truth(cfg: SimConfig, terrain: Terrain) -> Trajectory:
    n = cfg.steps()
    dt = cfg.dt
    t = np.arange(n) * dt

    # Heading profile: gentle serpentine turns to exercise 2-D nav.
    psi0 = np.deg2rad(cfg.heading0_deg)
    turn = np.deg2rad(9.0) * np.sin(2 * np.pi * t / 55.0) \
        + np.deg2rad(4.0) * np.sin(2 * np.pi * t / 23.0)
    heading = psi0 + turn

    speed = cfg.cruise_speed
    vel = np.stack([speed * np.cos(heading), speed * np.sin(heading)], axis=1)

    pos = np.zeros((n, 2))
    pos[0] = cfg.start_xy
    for k in range(1, n):
        pos[k] = pos[k - 1] + vel[k - 1] * dt

    # Specific force in nav frame = d(vel)/dt (gravity handled separately).
    acc = np.zeros((n, 2))
    acc[1:-1] = (vel[2:] - vel[:-2]) / (2 * dt)
    acc[0] = acc[1]
    acc[-1] = acc[-2]

    alt_msl = terrain.elevation(pos[:, 0], pos[:, 1]) + cfg.cruise_alt
    return Trajectory(t=t, pos=pos, vel=vel, acc=acc, heading=heading, alt_msl=alt_msl)
