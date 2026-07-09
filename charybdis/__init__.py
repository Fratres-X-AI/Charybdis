"""Charybdis — GPS-denied terrain-aided navigation.

Stable / Beta APIs are exported from this package. Experimental modules
(NN matcher, SLAM, swarm) live under :mod:`charybdis.experimental`.

Import tiers
------------
* **Core** — ``SimConfig``, ``Terrain``, ``Navigator``, ``NavEstimate``
* **Hybrid UUV** — ``HybridSensorFusion``, ``PatrolExecutor``, sensor types
* **Evaluation** — ``run_simulation``, ``run_montecarlo``, stress harness
* **Experimental** — ``import charybdis.experimental`` (opt-in, unstable)
"""
from __future__ import annotations

__version__ = "0.1.0"

# --- configuration & terrain -------------------------------------------------
from .config import SimConfig
from .terrain import Terrain
from .trajectory import Trajectory, generate_truth

# --- hybrid UUV foundation ---------------------------------------------------
from .modes import ModeManager, ModeManagerConfig, NavMode
from .sensors import (
    BathymetryMeasurement,
    DepthMeasurement,
    GpsMeasurement,
    ImuMeasurement,
    SensorPacket,
    SensorQuality,
    VelocityMeasurement,
)
from .fusion import HybridFusionConfig, HybridNavState, HybridSensorFusion
from .patrol import PatrolCommand, PatrolExecutor, PatrolRoute, Waypoint

# --- GDI navigation ----------------------------------------------------------
from .imu import IMU, ImuSample
from .ins import StrapdownINS
from .tercom import Tercom, TercomFix
from .ekf import NavEKF
from .pf import TerrainParticleFilter
from .pmf import TerrainPointMassFilter
from .navigator import Navigator, NavEstimate

# --- simulation & evaluation -------------------------------------------------
from .simulation import run_simulation, SimResult
from .evaluate import run_montecarlo, MonteCarloResult
from .stress import (
    default_stress_cases,
    evaluate_gates,
    run_stress_case,
    run_stress_harness,
    stress_report,
)

# --- advanced / supporting (submodule import also fine) ----------------------
from .estimation import (
    InnovationMonitor,
    cluster_modes,
    covariance_intersection,
    grid_multimodality,
    nees,
    stochastic_linearize,
    terrain_meas_var,
)
from .action_envelope import ActionEnvelope, ACTIONS, compute_action_envelope
from .pcrb import (
    efficiency_report,
    filter_efficiency,
    navigability_map,
    posterior_crb,
    terrain_fisher_information,
)
from .imu_model import (
    IMU_GRADES,
    allan_deviation,
    apply_imu_grade,
    characterize_allan,
    grade_allan_table,
)
from .bathy import (
    load_bathymetry,
    load_gebco_netcdf,
    load_npz,
    terrain_from_grid,
    terrain_suitability,
)

__all__ = [
    "__version__",
    # core
    "SimConfig",
    "Terrain",
    "Trajectory",
    "generate_truth",
    "Navigator",
    "NavEstimate",
    "NavEKF",
    "TerrainParticleFilter",
    "TerrainPointMassFilter",
    "Tercom",
    "TercomFix",
    "IMU",
    "ImuSample",
    "StrapdownINS",
    # hybrid UUV
    "NavMode",
    "ModeManager",
    "ModeManagerConfig",
    "SensorQuality",
    "ImuMeasurement",
    "GpsMeasurement",
    "DepthMeasurement",
    "VelocityMeasurement",
    "BathymetryMeasurement",
    "SensorPacket",
    "HybridFusionConfig",
    "HybridNavState",
    "HybridSensorFusion",
    "Waypoint",
    "PatrolRoute",
    "PatrolCommand",
    "PatrolExecutor",
    # simulation & evaluation
    "run_simulation",
    "SimResult",
    "run_montecarlo",
    "MonteCarloResult",
    "default_stress_cases",
    "run_stress_case",
    "run_stress_harness",
    "stress_report",
    "evaluate_gates",
    # supporting
    "InnovationMonitor",
    "covariance_intersection",
    "cluster_modes",
    "grid_multimodality",
    "nees",
    "stochastic_linearize",
    "terrain_meas_var",
    "ActionEnvelope",
    "ACTIONS",
    "compute_action_envelope",
    "terrain_fisher_information",
    "navigability_map",
    "posterior_crb",
    "filter_efficiency",
    "efficiency_report",
    "IMU_GRADES",
    "apply_imu_grade",
    "allan_deviation",
    "characterize_allan",
    "grade_allan_table",
    "load_bathymetry",
    "load_gebco_netcdf",
    "load_npz",
    "terrain_from_grid",
    "terrain_suitability",
]
