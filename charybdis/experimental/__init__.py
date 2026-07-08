"""Experimental Charybdis modules (opt-in).

These APIs are unstable. Prefer:

    from charybdis.experimental import run_swarm, init_slam, build_model

Do not rely on them from production Navigator paths until promoted in
docs/MATURITY.md.
"""
from __future__ import annotations

from .slam import (SlamState, gicp_align, init_slam, slam_step, optimize,
                   position_error)
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


def __getattr__(name: str):
    # Lazy: avoid importing torch unless nn_matcher symbols are requested.
    if name in {
        "PATCH", "SPAN", "build_model", "train", "load_model", "match_position",
        "predict_offset", "extract_patch", "extract_patches_batch",
        "extract_pair_batch", "eval_hard",
    }:
        from . import nn_matcher
        return getattr(nn_matcher, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
