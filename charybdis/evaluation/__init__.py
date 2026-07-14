"""Public Monte Carlo evaluation and stress-test entry points."""

from __future__ import annotations

from .confidence import (
    ValidationAssessment,
    assess_validation,
    bootstrap_percentile_interval,
    wilson_interval,
)
from .deep import (
    DEEP_VALIDATION_SCENARIOS,
    assess_deep_validation,
    run_hybrid_deep_montecarlo,
)
from .deep_scenarios import (
    DeepValidationGates,
    build_deep_validation_scenario,
    deep_validation_gates,
)
from .evaluate import FILTERS, MonteCarloResult, run_montecarlo
from .hybrid import HybridMonteCarloResult, run_hybrid_montecarlo
from .packet_replay import (
    ReplayLog,
    ReplayManifest,
    assert_replay_matches,
    load_replay_log,
    packet_from_dict,
    packet_to_dict,
    record_harbor_packets,
    replay_packets,
    save_replay_log,
)
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
    "DEEP_VALIDATION_SCENARIOS",
    "DeepValidationGates",
    "assess_deep_validation",
    "build_deep_validation_scenario",
    "deep_validation_gates",
    "run_hybrid_deep_montecarlo",
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
    "ReplayLog",
    "ReplayManifest",
    "assert_replay_matches",
    "load_replay_log",
    "packet_from_dict",
    "packet_to_dict",
    "record_harbor_packets",
    "replay_packets",
    "save_replay_log",
]
