"""Simulation and filter configuration."""
from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np


@dataclass
class SimConfig:
    # --- Timing ---
    dt: float = 0.02                # IMU / propagation step [s] (50 Hz)
    duration: float = 180.0         # total flight time [s]
    seed: int = 7

    # --- Terrain (local ENU grid, metres) ---
    terrain_size: float = 40_000.0  # square side length [m]
    terrain_res: float = 25.0       # DEM grid spacing [m]
    terrain_relief: float = 350.0   # peak-to-trough relief scale [m]

    # --- Truth trajectory ---
    start_xy: tuple[float, float] = (4_000.0, 4_000.0)
    cruise_speed: float = 230.0     # [m/s]
    cruise_alt: float = 600.0       # height above mean terrain [m]
    heading0_deg: float = 38.0

    # --- IMU error model ---
    accel_noise: float = 0.08       # white noise std [m/s^2 /sqrt(Hz)]
    accel_bias0: float = 0.05       # initial bias std [m/s^2]
    accel_bias_rw: float = 0.002    # bias random-walk [m/s^2 /sqrt(s)]
    gyro_noise: float = 0.02        # [deg/s]
    heading_bias0_deg: float = 0.4

    # --- Altimeters (terrain measurement chain) ---
    baro_noise: float = 3.0         # barometric altitude noise std [m]
    radar_noise: float = 1.5        # radar altimeter (AGL) noise std [m]

    # --- TERCOM ---
    tercom_period: float = 6.0      # seconds between correlation fixes
    tercom_strip: int = 48          # samples per correlation strip
    tercom_search: float = 450.0    # +/- search half-window [m]
    tercom_search_step: float = 15.0

    # --- EKF ---
    trn_update: bool = True         # recursive single-point terrain update
    trn_period: float = 0.2         # seconds between TRN updates
    init_pos_std: float = 120.0     # initial position uncertainty [m]
    init_vel_std: float = 3.0
    init_pos_error: float = 0.0     # actual initial position error injected [m]
    gate_chi2: float = 13.8         # 2-dof 99.9% gate

    # --- Particle filter (terrain-aided, non-Gaussian) ---
    use_pf: bool = True             # run the particle filter alongside the EKF
    n_particles: int = 1500
    pf_neff_frac: float = 0.5       # resample when Neff/N drops below this
    pf_roughen: float = 0.2         # roughening coefficient after resampling
    pf_pos_floor: float = 12.0      # min position roughening [m] (anti-impoverishment)
    pf_vel_floor: float = 0.4       # min velocity roughening [m/s]
    pf_inject: float = 0.25         # fraction of particles relocalised on a fix
    pf_inject_std_max: float = 160.0  # skip injection if fix worse than this [m]

    def steps(self) -> int:
        return int(round(self.duration / self.dt))
