"""Surface/submerged mode management for hybrid UUV navigation."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class NavMode(StrEnum):
    SURFACE = "surface"
    SUBMERGED = "submerged"


@dataclass(frozen=True)
class ModeManagerConfig:
    surface_depth_m: float = 1.5
    submerged_depth_m: float = 3.0


class ModeManager:
    """Hysteretic mode selector.

    Depth decides the mode when no explicit route hint is provided. GPS
    availability is intentionally not the mode source; it is just a measurement
    quality input to fusion.
    """

    def __init__(self, cfg: ModeManagerConfig | None = None,
                 initial: NavMode = NavMode.SURFACE):
        self.cfg = cfg or ModeManagerConfig()
        self.mode = initial

    def update(self, *, depth_m: float | None = None,
               hint: NavMode | None = None) -> NavMode:
        if hint is not None:
            self.mode = hint
            return self.mode

        if depth_m is None:
            return self.mode

        if self.mode == NavMode.SURFACE and depth_m >= self.cfg.submerged_depth_m:
            self.mode = NavMode.SUBMERGED
        elif self.mode == NavMode.SUBMERGED and depth_m <= self.cfg.surface_depth_m:
            self.mode = NavMode.SURFACE
        return self.mode
