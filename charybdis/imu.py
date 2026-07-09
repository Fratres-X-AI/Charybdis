"""IMU and altimeter sensor models.

The IMU produces specific-force and heading-rate measurements corrupted by
bias (random walk) and white noise. Altimeters yield the terrain-elevation
observation used by TERCOM / TRN:  ground_elev = alt_msl - agl.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import SimConfig
from .terrain import Terrain
from .trajectory import Trajectory


@dataclass
class ImuSample:
    accel: np.ndarray  # measured specific force, nav frame [m/s^2]
    heading: float  # measured heading [rad]
    baro_alt: float  # measured MSL altitude [m]
    agl: float  # measured height above ground (radar alt) [m]
    ground_elev: float  # derived terrain elevation beneath vehicle [m]


class IMU:
    """Stateful sensor simulator producing measurements from truth."""

    def __init__(self, cfg: SimConfig, terrain: Terrain):
        self.cfg = cfg
        self.terrain = terrain
        self.rng = np.random.default_rng(cfg.seed + 101)
        self.accel_bias = self.rng.normal(0.0, cfg.accel_bias0, size=2)
        self.heading_bias = np.deg2rad(self.rng.normal(0.0, cfg.heading_bias0_deg))
        self.svp_bias = (
            self.rng.normal(0.0, cfg.svp_bias0, size=2)
            if cfg.svp_tidal_bias
            else np.zeros(2)
        )

    def sample(self, truth: Trajectory, k: int) -> ImuSample:
        cfg = self.cfg
        dt = cfg.dt
        # Bias random walk.
        self.accel_bias += self.rng.normal(0.0, cfg.accel_bias_rw * np.sqrt(dt), size=2)
        if cfg.svp_tidal_bias:
            self.svp_bias += self.rng.normal(0.0, cfg.svp_bias_rw * np.sqrt(dt), size=2)
        accel = (
            truth.acc[k]
            + self.accel_bias
            + (self.svp_bias if cfg.svp_tidal_bias else 0.0)
            + self.rng.normal(0.0, cfg.accel_noise / np.sqrt(dt), size=2)
        )
        heading = (
            truth.heading[k]
            + self.heading_bias
            + np.deg2rad(self.rng.normal(0.0, cfg.gyro_noise))
        )

        true_ground = float(self.terrain.elevation(truth.pos[k, 0], truth.pos[k, 1]))
        agl_true = truth.alt_msl[k] - true_ground
        baro_alt = truth.alt_msl[k] + self.rng.normal(0.0, cfg.baro_noise)
        agl = agl_true + self.rng.normal(0.0, cfg.radar_noise)
        ground_elev = baro_alt - agl
        return ImuSample(
            accel=accel,
            heading=heading,
            baro_alt=baro_alt,
            agl=agl,
            ground_elev=ground_elev,
        )
