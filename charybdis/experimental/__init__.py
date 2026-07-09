"""Minimal opt-in API for unstable Charybdis research modules.

SLAM and swarm entry points are explicit exports. Neural matcher names are
resolved lazily so importing this package does not import PyTorch; import them
directly from :mod:`charybdis.experimental.nn_matcher` for discoverability.

Do not depend on these APIs from production navigation paths.
"""
from __future__ import annotations

from typing import Any

from .slam import (
    SlamState,
    gicp_align,
    init_slam,
    optimize,
    position_error,
    slam_step,
)
from .swarm import SwarmConfig, SwarmResult, montecarlo_swarm, run_swarm

__all__ = [
    "SlamState",
    "gicp_align",
    "init_slam",
    "slam_step",
    "optimize",
    "position_error",
    "SwarmConfig",
    "SwarmResult",
    "montecarlo_swarm",
    "run_swarm",
]

_NN_MATCHER_EXPORTS = {
    "PATCH",
    "SPAN",
    "build_model",
    "train",
    "load_model",
    "match_position",
    "predict_offset",
    "extract_patch",
    "extract_patches_batch",
    "extract_pair_batch",
    "eval_hard",
}


def __getattr__(name: str) -> Any:
    """Resolve optional neural matcher symbols without eagerly loading PyTorch."""
    if name in _NN_MATCHER_EXPORTS:
        from . import nn_matcher

        return getattr(nn_matcher, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
