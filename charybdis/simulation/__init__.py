"""Public simulation entry points for legacy and hybrid navigation."""

from __future__ import annotations

from .deep import (
    HybridDeepConfig,
    HybridDeepResult,
    build_synthetic_deep_map,
    run_hybrid_deep_simulation,
)
from .hybrid import (
    HybridHarborConfig,
    HybridHarborResult,
    build_synthetic_harbor_map,
    run_hybrid_harbor_simulation,
)
from .simulation import SimResult, run_simulation

__all__ = [
    "SimResult",
    "run_simulation",
    "HybridHarborConfig",
    "HybridHarborResult",
    "build_synthetic_harbor_map",
    "run_hybrid_harbor_simulation",
    "HybridDeepConfig",
    "HybridDeepResult",
    "build_synthetic_deep_map",
    "run_hybrid_deep_simulation",
]
