"""Compatibility shim — prefer ``charybdis.experimental.swarm``."""
from __future__ import annotations

import warnings

warnings.warn(
    "charybdis.swarm is experimental; import from charybdis.experimental.swarm",
    DeprecationWarning,
    stacklevel=2,
)

from .experimental.swarm import *  # noqa: F401,F403
from .experimental.swarm import (SwarmConfig, SwarmResult, montecarlo_swarm,
                                 run_swarm)

__all__ = [
    "SwarmConfig", "SwarmResult", "montecarlo_swarm", "run_swarm",
]
