"""Charybdis - GPS-Denied Interceptor Navigation.

Inertial (dead-reckoning) + Terrain-Contour Matching (TERCOM) fused with an
Extended Kalman Filter for navigation without GNSS.
"""
from .config import SimConfig
from .terrain import Terrain
from .trajectory import Trajectory, generate_truth
from .imu import IMU, ImuSample
from .ins import StrapdownINS
from .tercom import Tercom, TercomFix
from .ekf import NavEKF
from .pf import TerrainParticleFilter
from .navigator import Navigator
from .simulation import run_simulation, SimResult
from .evaluate import run_montecarlo, MonteCarloResult

__all__ = [
    "SimConfig",
    "Terrain",
    "Trajectory",
    "generate_truth",
    "IMU",
    "ImuSample",
    "StrapdownINS",
    "Tercom",
    "TercomFix",
    "NavEKF",
    "TerrainParticleFilter",
    "Navigator",
    "run_simulation",
    "SimResult",
    "run_montecarlo",
    "MonteCarloResult",
]
