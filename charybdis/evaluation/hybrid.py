"""Statistical summaries for deterministic hybrid harbor simulations."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from multiprocessing import Pool
from typing import Any

import numpy as np
from numpy.typing import NDArray

from ..parallel import pool_workers
from ..simulation.hybrid import HybridHarborConfig, run_hybrid_harbor_simulation

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class HybridMonteCarloResult:
    """Aggregated primary-stack validation metrics across fixed seeds."""

    seeds: tuple[int, ...]
    final_error_m: FloatArray
    max_error_m: FloatArray
    final_depth_error_m: FloatArray
    position_anees: FloatArray
    depth_anees: FloatArray
    route_complete: NDArray[np.bool_]
    filter_healthy: NDArray[np.bool_]
    fusion_rejections: NDArray[np.int64]

    @property
    def cep50_m(self) -> float:
        """Median final horizontal error."""
        return float(np.percentile(self.final_error_m, 50.0))

    @property
    def cep95_m(self) -> float:
        """95th-percentile final horizontal error."""
        return float(np.percentile(self.final_error_m, 95.0))

    @property
    def depth_cep95_m(self) -> float:
        """95th-percentile absolute final depth error."""
        return float(np.percentile(self.final_depth_error_m, 95.0))

    @property
    def route_completion_rate(self) -> float:
        """Fraction of simulations that completed the route."""
        return float(np.mean(self.route_complete))

    @property
    def healthy_rate(self) -> float:
        """Fraction of final estimates classified healthy."""
        return float(np.mean(self.filter_healthy))

    def divergence_rate(self, threshold_m: float = 50.0) -> float:
        """Fraction of final errors exceeding a supplied threshold."""
        if not np.isfinite(threshold_m) or threshold_m <= 0.0:
            raise ValueError("threshold_m must be finite and positive")
        return float(np.mean(self.final_error_m > threshold_m))

    def to_dict(self) -> dict[str, Any]:
        """Return a stable JSON-compatible summary."""
        return {
            "seeds": list(self.seeds),
            "runs": len(self.seeds),
            "cep50_m": self.cep50_m,
            "cep95_m": self.cep95_m,
            "depth_cep95_m": self.depth_cep95_m,
            "route_completion_rate": self.route_completion_rate,
            "healthy_rate": self.healthy_rate,
            "position_anees_mean": float(np.mean(self.position_anees)),
            "depth_anees_mean": float(np.mean(self.depth_anees)),
            "divergence_rate_50m": self.divergence_rate(),
            "fusion_rejections_total": int(np.sum(self.fusion_rejections)),
        }


def run_hybrid_montecarlo(
    cfg: HybridHarborConfig | None = None,
    *,
    seeds: Iterable[int],
    workers: int = 1,
) -> HybridMonteCarloResult:
    """Run a fixed seed set, capped at 31 workers and forced serial in pytest."""
    base = cfg or HybridHarborConfig()
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
    )


def _run_seed(job: tuple[HybridHarborConfig, int]) -> dict[str, Any]:
    cfg, seed = job
    return run_hybrid_harbor_simulation(replace(cfg, seed=seed)).summary()


__all__ = ["HybridMonteCarloResult", "run_hybrid_montecarlo"]
