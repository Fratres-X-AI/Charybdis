"""Charybdis high-level public API.

Only common entry points are exported here. Import sensor models and route
types from :mod:`charybdis.hybrid`, interceptor filters from
:mod:`charybdis.legacy`, and research tooling from its explicit submodule.
"""
from __future__ import annotations

from .config import SimConfig
from .hybrid import (
    HybridNavState,
    HybridSensorFusion,
    NavMode,
    PatrolExecutor,
    SensorPacket,
)
from .legacy import NavEstimate, Navigator
from .simulation import (
    run_hybrid_harbor_simulation,
    run_simulation,
)
from .terrain import Terrain
from .trajectory import generate_truth
from .version import __version__

__all__ = [
    "__version__",
    "SimConfig",
    "Terrain",
    "generate_truth",
    "NavMode",
    "SensorPacket",
    "HybridNavState",
    "HybridSensorFusion",
    "PatrolExecutor",
    "Navigator",
    "NavEstimate",
    "run_simulation",
    "run_hybrid_harbor_simulation",
]
