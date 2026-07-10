"""Deterministic confidence bounds for release validation metrics."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Any

import numpy as np
from numpy.typing import ArrayLike

from .hybrid import HybridMonteCarloResult
from .scenarios import ValidationGates


@dataclass(frozen=True)
class ValidationAssessment:
    """Confidence-bounded gate outcome for one scenario."""

    passed: bool
    checks: dict[str, dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible assessment."""
        return {"passed": self.passed, "checks": self.checks}


def wilson_interval(
    successes: int,
    total: int,
    *,
    z: float = 1.959963984540054,
) -> tuple[float, float]:
    """Return the two-sided Wilson score interval for a binomial rate."""
    if total <= 0:
        raise ValueError("total must be positive")
    if not 0 <= successes <= total:
        raise ValueError("successes must be between zero and total")
    if not np.isfinite(z) or z <= 0.0:
        raise ValueError("z must be finite and positive")
    probability = successes / total
    denominator = 1.0 + z**2 / total
    center = (probability + z**2 / (2.0 * total)) / denominator
    margin = (
        z
        * sqrt(probability * (1.0 - probability) / total + z**2 / (4.0 * total**2))
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def bootstrap_percentile_interval(
    values: ArrayLike,
    percentile: float,
    *,
    confidence: float = 0.95,
    resamples: int = 4_000,
    seed: int = 20_260_709,
) -> tuple[float, float]:
    """Return a deterministic percentile-bootstrap interval."""
    samples = np.asarray(values, dtype=np.float64)
    if samples.ndim != 1 or samples.size < 2 or not np.all(np.isfinite(samples)):
        raise ValueError("values must be a finite one-dimensional sample")
    if not 0.0 <= percentile <= 100.0:
        raise ValueError("percentile must be in [0, 100]")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be in (0, 1)")
    if resamples <= 0:
        raise ValueError("resamples must be positive")

    rng = np.random.default_rng(seed)
    estimates = np.empty(resamples, dtype=np.float64)
    batch_size = min(500, resamples)
    for start in range(0, resamples, batch_size):
        stop = min(start + batch_size, resamples)
        indices = rng.integers(
            0,
            samples.size,
            size=(stop - start, samples.size),
        )
        estimates[start:stop] = np.percentile(
            samples[indices],
            percentile,
            axis=1,
        )
    alpha = (1.0 - confidence) / 2.0
    lower, upper = np.quantile(estimates, [alpha, 1.0 - alpha])
    return float(lower), float(upper)


def assess_validation(
    result: HybridMonteCarloResult,
    gates: ValidationGates,
) -> ValidationAssessment:
    """Apply pre-declared release gates using conservative confidence bounds."""
    runs = len(result.seeds)
    completion = wilson_interval(int(np.sum(result.route_complete)), runs)
    healthy = wilson_interval(int(np.sum(result.filter_healthy)), runs)
    divergences = int(np.sum(result.final_error_m > 50.0))
    divergence = wilson_interval(divergences, runs)
    cep95 = bootstrap_percentile_interval(result.final_error_m, 95.0)
    depth95 = bootstrap_percentile_interval(
        np.abs(result.final_depth_error_m),
        95.0,
        seed=20_260_710,
    )
    gps_jump95 = bootstrap_percentile_interval(
        result.max_gps_reacquisition_jump_m,
        95.0,
        seed=20_260_711,
    )
    checks = {
        "route_completion_lower": _minimum_check(
            completion[0],
            gates.min_route_completion_rate,
            interval=completion,
        ),
        "healthy_lower": _minimum_check(
            healthy[0],
            gates.min_healthy_rate,
            interval=healthy,
        ),
        "divergence_upper": _maximum_check(
            divergence[1],
            gates.max_divergence_rate,
            interval=divergence,
        ),
        "cep95_upper_m": _maximum_check(
            cep95[1],
            gates.max_cep95_m,
            interval=cep95,
        ),
        "depth_cep95_upper_m": _maximum_check(
            depth95[1],
            gates.max_depth_cep95_m,
            interval=depth95,
        ),
        "gps_reacquisition_jump_upper_m": _maximum_check(
            gps_jump95[1],
            gates.max_gps_reacquisition_jump_m,
            interval=gps_jump95,
        ),
    }
    return ValidationAssessment(
        passed=all(bool(check["passed"]) for check in checks.values()),
        checks=checks,
    )


def _minimum_check(
    observed: float,
    threshold: float,
    *,
    interval: tuple[float, float],
) -> dict[str, Any]:
    return {
        "passed": observed >= threshold,
        "observed": observed,
        "threshold": threshold,
        "interval_95": list(interval),
        "operator": ">=",
    }


def _maximum_check(
    observed: float,
    threshold: float,
    *,
    interval: tuple[float, float],
) -> dict[str, Any]:
    return {
        "passed": observed <= threshold,
        "observed": observed,
        "threshold": threshold,
        "interval_95": list(interval),
        "operator": "<=",
    }


__all__ = [
    "ValidationAssessment",
    "assess_validation",
    "bootstrap_percentile_interval",
    "wilson_interval",
]
