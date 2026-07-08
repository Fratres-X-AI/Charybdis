"""Compatibility shim — prefer ``charybdis.experimental.nn_matcher``."""
from __future__ import annotations

import warnings

warnings.warn(
    "charybdis.nn_matcher is experimental; import from "
    "charybdis.experimental.nn_matcher",
    DeprecationWarning,
    stacklevel=2,
)

from .experimental.nn_matcher import *  # noqa: F401,F403
