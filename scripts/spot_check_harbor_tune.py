#!/usr/bin/env python3
"""Quick local spot-check for tuned harbor scenarios."""

from __future__ import annotations

from charybdis.evaluation import (
    assess_validation,
    build_validation_scenario,
    load_validation_seeds,
    run_hybrid_montecarlo,
    validation_gates,
)

for name in ("sparse_outlier_bathymetry", "repeated_mode_transitions"):
    cfg = build_validation_scenario(name)
    seeds = load_validation_seeds("validation/seeds_v1.txt", limit=64)
    results = run_hybrid_montecarlo(cfg, seeds=seeds, workers=1)
    assessment = assess_validation(results, validation_gates(name))
    print(name)
    print(f"  cep95 {results.cep95_m:.3f}")
    print(f"  pos_anees {float(results.position_anees.mean()):.3f}")
    print(f"  divergence {results.divergence_rate():.4f}")
    print(f"  divergence_upper {assessment.checks['divergence_upper']['observed']:.4f}")
    print(f"  passed {assessment.passed}")
