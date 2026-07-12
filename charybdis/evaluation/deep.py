"""Statistical summaries for deterministic hybrid deep-ocean simulations."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from multiprocessing import Pool
from typing import Any

import numpy as np

from ..parallel import pool_workers
from ..simulation.deep import HybridDeepConfig, run_hybrid_deep_simulation
from .confidence import ValidationAssessment, assess_validation
from .deep_scenarios import DEEP_VALIDATION_SCENARIOS, DeepValidationGates
from .hybrid import HybridMonteCarloResult
from .scenarios import ValidationGates


def run_hybrid_deep_montecarlo(
    cfg: HybridDeepConfig | None = None,
    *,
    seeds: Iterable[int],
    workers: int = 1,
) -> HybridMonteCarloResult:
    """Run a fixed seed set for deep-ocean scenarios."""
    base = cfg or HybridDeepConfig()
    seed_tuple = tuple(int(seed) for seed in seeds)
    if not seed_tuple or any(seed < 0 for seed in seed_tuple):
        raise ValueError("seeds must contain at least one non-negative integer")
    if len(set(seed_tuple)) != len(seed_tuple):
        raise ValueError("seeds must be unique")

    worker_count = pool_workers(workers)
    jobs = [(base, seed) for seed in seed_tuple]
    if worker_count == 1:
        summaries = [_run_seed(job) for job in jobs]
    else:
        with Pool(worker_count) as pool:
            summaries = pool.map(_run_seed, jobs)
    return HybridMonteCarloResult(
        seeds=seed_tuple,
        final_error_m=np.asarray(
            [summary["final_error_m"] for summary in summaries],
            dtype=np.float64,
        ),
        max_error_m=np.asarray(
            [summary["max_error_m"] for summary in summaries],
            dtype=np.float64,
        ),
        final_depth_error_m=np.asarray(
            [summary["final_depth_error_m"] for summary in summaries],
            dtype=np.float64,
        ),
        position_anees=np.asarray(
            [summary["position_anees"] for summary in summaries],
            dtype=np.float64,
        ),
        depth_anees=np.asarray(
            [summary["depth_anees"] for summary in summaries],
            dtype=np.float64,
        ),
        route_complete=np.asarray(
            [summary["route_complete"] for summary in summaries],
            dtype=np.bool_,
        ),
        filter_healthy=np.asarray(
            [summary["filter_healthy"] for summary in summaries],
            dtype=np.bool_,
        ),
        fusion_rejections=np.asarray(
            [summary["fusion_rejections"] for summary in summaries],
            dtype=np.int64,
        ),
        max_gps_reacquisition_jump_m=np.asarray(
            [summary["max_gps_reacquisition_jump_m"] for summary in summaries],
            dtype=np.float64,
        ),
    )


def assess_deep_validation(
    result: HybridMonteCarloResult,
    gates: DeepValidationGates,
) -> ValidationAssessment:
    """Apply deep-ocean gates using the shared confidence-bound machinery."""
    adapted = ValidationGates(
        max_cep95_m=gates.max_cep95_m,
        max_depth_cep95_m=gates.max_depth_cep95_m,
        min_route_completion_rate=gates.min_route_completion_rate,
        min_healthy_rate=gates.min_healthy_rate,
        max_divergence_rate=gates.max_divergence_rate,
        max_gps_reacquisition_jump_m=gates.max_gps_reacquisition_jump_m,
    )
    return assess_validation(result, adapted)


def _run_seed(job: tuple[HybridDeepConfig, int]) -> dict[str, Any]:
    cfg, seed = job
    return run_hybrid_deep_simulation(replace(cfg, seed=seed)).summary()


__all__ = [
    "DEEP_VALIDATION_SCENARIOS",
    "assess_deep_validation",
    "run_hybrid_deep_montecarlo",
]
