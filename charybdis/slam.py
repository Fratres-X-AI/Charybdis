"""Compatibility shim — prefer ``charybdis.experimental.slam``."""
from __future__ import annotations

import warnings

warnings.warn(
    "charybdis.slam is experimental; import from charybdis.experimental.slam",
    DeprecationWarning,
    stacklevel=2,
)

from .experimental.slam import *  # noqa: F401,F403
from .experimental.slam import (SlamState, gicp_align, init_slam, slam_step,
                                optimize, position_error)

__all__ = [
    "SlamState", "gicp_align", "init_slam", "slam_step", "optimize",
    "position_error",
]
