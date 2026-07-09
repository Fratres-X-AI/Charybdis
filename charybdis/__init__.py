"""Charybdis — GPS-denied terrain-aided navigation.

Public API tiers
----------------
* **Core** — ``SimConfig``, ``Terrain``, ``Trajectory``, ``IMU``, ``INS``
* **Hybrid UUV** (primary) — ``HybridSensorFusion``, ``PatrolExecutor``, sensors
* **Legacy interceptor** — ``Navigator``, ``NavEstimate``, TERCOM/EKF/PF/PMF
* **Simulation / evaluation** — ``run_simulation``, ``run_montecarlo``, stress

Advanced modules (``estimation``, ``pcrb``, ``bathy``, ``action_envelope``,
``imu_model``) are available via explicit submodule imports.
Experimental code lives under :mod:`charybdis.experimental`.
"""
from __future__ import annotations

__version__ = "0.1.0"

# --- core ----------------------------------------------------------------------
from .config import SimConfig
from .terrain import Terrain
from .trajectory import Trajectory, generate_truth
from .imu import IMU, ImuSample
from .ins import StrapdownINS

# --- hybrid UUV (primary) ------------------------------------------------------
from .hybrid import (
    BathymetryMeasurement,
    DepthMeasurement,
    GpsMeasurement,
    HybridFusionConfig,
    HybridNavState,
    HybridSensorFusion,
    ImuMeasurement,
    ModeManager,
    ModeManagerConfig,
    NavMode,
    PatrolCommand,
    PatrolExecutor,
    PatrolRoute,
    SensorPacket,
    SensorQuality,
    VelocityMeasurement,
    Waypoint,
)

# --- legacy interceptor navigation ---------------------------------------------
from .legacy import (
    NavEKF,
    NavEstimate,
    Navigator,
    TerrainParticleFilter,
    TerrainPointMassFilter,
    Tercom,
    TercomFix,
)

# --- simulation & evaluation ---------------------------------------------------
from .simulation import (
    HybridHarborConfig,
    HybridHarborResult,
    SimResult,
    run_hybrid_harbor_simulation,
    run_simulation,
)
from .evaluation import (
    MonteCarloResult,
    default_stress_cases,
    evaluate_gates,
    run_montecarlo,
    run_stress_case,
    run_stress_harness,
    stress_report,
)

__all__ = [
    "__version__",
    # core
    "SimConfig",
    "Terrain",
    "Trajectory",
    "generate_truth",
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
    "HybridHarborConfig",
    "HybridHarborResult",
    "run_hybrid_harbor_simulation",
    # legacy
    "Navigator",
    "NavEstimate",
    "NavEKF",
    "TerrainParticleFilter",
    "TerrainPointMassFilter",
    "Tercom",
    "TercomFix",
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
]
