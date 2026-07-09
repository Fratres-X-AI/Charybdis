"""Public Monte Carlo evaluation and stress-test entry points."""

from __future__ import annotations

from .confidence import (
    ValidationAssessment,
    assess_validation,
    bootstrap_percentile_interval,
    wilson_interval,
)
from .evaluate import FILTERS, MonteCarloResult, run_montecarlo
from .hybrid import HybridMonteCarloResult, run_hybrid_montecarlo
from .scenarios import (
    VALIDATION_SCENARIOS,
    ValidationGates,
    build_validation_scenario,
    validation_gates,
)
from .stress import (
    StressCase,
    StressGates,
    StressResult,
    adversarial_terrain,
    default_stress_cases,
    evaluate_gates,
    run_stress_case,
    run_stress_harness,
    stress_report,
)
from .validation import (
    ValidationManifest,
    load_validation_seeds,
    write_validation_artifact,
)

__all__ = [
    "FILTERS",
    "ValidationAssessment",
    "assess_validation",
    "bootstrap_percentile_interval",
    "wilson_interval",
    "MonteCarloResult",
    "run_montecarlo",
    "HybridMonteCarloResult",
    "run_hybrid_montecarlo",
    "VALIDATION_SCENARIOS",
    "ValidationGates",
    "build_validation_scenario",
    "validation_gates",
    "StressCase",
    "StressGates",
    "StressResult",
    "adversarial_terrain",
    "default_stress_cases",
    "evaluate_gates",
    "run_stress_case",
    "run_stress_harness",
    "stress_report",
    "ValidationManifest",
    "load_validation_seeds",
    "write_validation_artifact",
]
