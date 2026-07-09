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

    # --- SVP / tidal unmodeled dynamics (slow horizontal accel bias) ---
    svp_tidal_bias: bool = False    # enable slow sound-velocity / tidal bias state
    svp_bias0: float = 0.02       # initial SVP bias std [m/s^2]
    svp_bias_rw: float = 0.0008   # SVP bias random walk [m/s^2 /sqrt(s)]

    # --- Altimeters (terrain measurement chain) ---
    baro_noise: float = 3.0         # barometric altitude noise std [m]
    radar_noise: float = 1.5        # radar altimeter (AGL) noise std [m]

    # --- TERCOM ---
    use_tercom: bool = True         # batch correlation position fixes (off => grid/TRN only)
    tercom_period: float = 6.0      # seconds between correlation fixes
    tercom_strip: int = 48          # samples per correlation strip
    tercom_search: float = 450.0    # +/- search half-window [m]
    tercom_search_step: float = 15.0
    tercom_min_cost_margin: float = 0.25  # reject nearly-tied correlation peaks [m]

    # --- Map / bathymetry uncertainty (map is NOT ground truth) ---
    map_sigma: float = 2.0          # stored-DEM vertical error std [m]
    map_interp_frac: float = 0.5    # sub-cell interpolation error as frac of a
                                    # cell, projected through terrain slope

    # --- EKF ---
    trn_update: bool = True         # recursive single-point terrain update
    trn_period: float = 0.2         # seconds between TRN updates
    init_pos_std: float = 120.0     # initial position uncertainty [m]
    init_vel_std: float = 3.0
    init_pos_error: float = 0.0     # actual initial position error injected [m]
    gate_chi2: float = 13.8         # 2-dof 99.9% gate

    # --- EKF stochastic (unscented) linearisation of the DEM ---
    # Point-slope Jacobians are inaccurate exactly when the position error is
    # large (the divergence regime); fit the slope over the position prior and
    # add the residual as measurement noise for consistency.
    ekf_stochastic_lin: bool = True
    ekf_sl_kappa: float = 1.0       # unscented spread parameter
    ekf_sl_min_frac: float = 0.75   # min sigma-point radius as frac of a cell
    ekf_sl_max_radius: float = 400.0  # max sigma-point radius [m]

    # --- Adaptive process noise (innovation-based / covariance matching) ---
    adapt_q: bool = True            # scale Q from recent innovation statistics
    adapt_q_window: int = 40        # innovation window length [updates]
    adapt_q_min: float = 1.0        # never shrink Q (guards overconfidence)
    adapt_q_max: float = 12.0       # cap Q inflation
    adapt_q_min_count: int = 15     # updates required before adapting
    adapt_q_terrain: bool = True    # extra Q inflation in low-information terrain
    adapt_q_terrain_max: float = 4.0
    adapt_q_terrain_ref: float = 0.06  # slope Fisher scale for "informative"

    # --- EKF <-> PF interaction (divergence detection + recovery) ---
    filter_fusion: bool = True      # let the robust filters rescue the EKF
    fusion_period: float = 1.0      # seconds between coordination checks
    ekf_div_maha: float = 30.0      # cross-filter disagreement gate (2-dof)
    ekf_div_nis: float = 5.0        # sustained EKF NIS ratio => faulted
    ekf_reset_infl: float = 1.5     # covariance inflation on an EKF reset
    ekf_reset_cooldown: float = 4.0 # seconds between resets (anti-thrash)
    fusion_ci_help_std: float = 60.0  # soft CI correction only when EKF this lost [m]
    ref_confident_std: float = 160.0  # reference trusted for reset below this [m]
    ref_confident_neff: float = 0.30  # PF Neff/N required to trust a reset

    # --- Multi-hypothesis / mode management (ambiguous terrain) ---
    mode_mgmt: bool = True          # detect PF ambiguity and adapt behaviour
    mode_period: float = 1.0        # seconds between ambiguity checks
    mode_cluster_radius: float = 120.0  # particle clustering radius [m]
    mode_mass_frac: float = 0.15    # min mass fraction for a distinct mode
    mode_grid_frac: float = 0.45    # grid peak threshold (PMF multimodality)

    # --- Particle filter (terrain-aided, non-Gaussian) ---
    use_pf: bool = True             # run the particle filter alongside the EKF
    n_particles: int = 1500
    pf_neff_frac: float = 0.5       # resample when Neff/N drops below this
    pf_roughen: float = 0.2         # roughening coefficient after resampling
    pf_pos_floor: float = 12.0      # min position roughening [m] (anti-impoverishment)
    pf_vel_floor: float = 0.4       # min velocity roughening [m/s]
    pf_inject: float = 0.25         # fraction of particles relocalised on a fix
    pf_inject_std_max: float = 160.0  # skip injection if fix worse than this [m]

    # --- Point-mass filter (legacy comparison, not core recovery path) ---
    use_pmf: bool = True            # keep available for existing eval scripts
    pmf_res: float = 25.0           # grid spacing [m]
    pmf_halfwidth: float = 500.0    # grid half-window [m] (auto-grows w/ init_pos_std)
    pmf_meas_dof: float = 5.0       # Student-t dof for robust terrain likelihood
    pmf_process_infl: float = 1.0   # process-noise inflation (anti-overconfidence)
    pmf_meas_infl: float = 1.5      # terrain measurement-noise inflation (NEES/robustness)
    pmf_use_tercom: bool = False    # feed batch TERCOM fixes to the PMF; off by default
                                    # since the grid update already does robust,
                                    # full-likelihood terrain referencing and a single
                                    # correlation peak can be ambiguous/wrong

    def steps(self) -> int:
        return int(round(self.duration / self.dt))
