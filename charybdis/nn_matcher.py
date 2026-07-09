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
from .experimental.nn_matcher import (
    PATCH, SPAN, build_model, train, load_model, match_position,
    predict_offset, extract_patch, extract_patches_batch,
    extract_pair_batch, eval_hard,
)

__all__ = [
    "PATCH", "SPAN", "build_model", "train", "load_model", "match_position",
    "predict_offset", "extract_patch", "extract_patches_batch",
    "extract_pair_batch", "eval_hard",
]
