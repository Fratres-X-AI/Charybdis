"""Surface/submerged mode management for hybrid UUV navigation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np


class NavMode(StrEnum):
    SURFACE = "surface"
    SUBMERGED = "submerged"


@dataclass(frozen=True)
class ModeManagerConfig:
    """Depth hysteresis and route-hint policy."""

    surface_depth_m: float = 1.5
    submerged_depth_m: float = 3.0
    hint_overrides_depth: bool = False

    def __post_init__(self) -> None:
        if (
            not np.isfinite(self.surface_depth_m)
            or not np.isfinite(self.submerged_depth_m)
            or self.surface_depth_m < 0.0
            or self.submerged_depth_m <= self.surface_depth_m
        ):
            raise ValueError(
                "mode depths must be finite, non-negative, and strictly ordered"
            )
        if not isinstance(self.hint_overrides_depth, bool):
            raise TypeError("hint_overrides_depth must be bool")


class ModeManager:
    """Hysteretic mode selector.

    Depth is authoritative by default. Route hints may select a mode only inside
    the hysteresis band unless ``hint_overrides_depth`` is explicitly enabled.
    GPS availability is measurement quality, never a mode source.
    """

    def __init__(
        self,
        cfg: ModeManagerConfig | None = None,
        initial: NavMode = NavMode.SURFACE,
    ) -> None:
        self.cfg = cfg or ModeManagerConfig()
        self.mode = NavMode(initial)

    def update(
        self,
        *,
        depth_m: float | None = None,
        hint: NavMode | None = None,
    ) -> NavMode:
        """Select mode while enforcing the configured depth safety policy."""
        if hint is not None:
            hint = NavMode(hint)
        if hint is not None and self.cfg.hint_overrides_depth:
            self.mode = hint
            return self.mode

        if depth_m is None:
            if hint is not None:
                self.mode = hint
            return self.mode

        depth = float(depth_m)
        if not np.isfinite(depth) or depth < 0.0:
            raise ValueError("depth_m must be finite and non-negative")

        if depth >= self.cfg.submerged_depth_m:
            self.mode = NavMode.SUBMERGED
        elif depth <= self.cfg.surface_depth_m:
            self.mode = NavMode.SURFACE
        elif hint is not None:
            self.mode = hint
        return self.mode
