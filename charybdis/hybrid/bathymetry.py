"""Deterministic terrain-profile aiding for hybrid UUV navigation.

Coordinates use a local navigation frame in metres. Map and observation depths
are positive down relative to the same vertical datum.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import cast

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .sensors import BathymetryMeasurement

FloatArray = NDArray[np.float64]


def _readonly(value: ArrayLike, *, name: str) -> FloatArray:
    array = np.array(value, dtype=np.float64, copy=True)
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be finite")
    array.setflags(write=False)
    return array


def _positive(value: float, *, name: str, allow_zero: bool = False) -> float:
    result = float(value)
    invalid = result < 0.0 if allow_zero else result <= 0.0
    if not np.isfinite(result) or invalid:
        relation = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{name} must be finite and {relation}")
    return result


@dataclass(frozen=True)
class BathymetryMap:
    """Regular positive-down bathymetry grid in a local metric frame."""

    depth_grid_m: ArrayLike
    resolution_m: float
    origin_xy_m: tuple[float, float] = (0.0, 0.0)

    def __post_init__(self) -> None:
        grid = _readonly(self.depth_grid_m, name="depth_grid_m")
        if grid.ndim != 2 or min(grid.shape) < 3:
            raise ValueError("depth_grid_m must be a 2D grid at least 3x3")
        resolution = _positive(self.resolution_m, name="resolution_m")
        origin = tuple(float(value) for value in self.origin_xy_m)
        if len(origin) != 2 or not np.all(np.isfinite(origin)):
            raise ValueError("origin_xy_m must contain two finite values")
        object.__setattr__(self, "depth_grid_m", grid)
        object.__setattr__(self, "resolution_m", resolution)
        object.__setattr__(self, "origin_xy_m", origin)

    @property
    def shape(self) -> tuple[int, int]:
        """Grid shape as ``(rows, columns)``."""
        rows, columns = cast(FloatArray, self.depth_grid_m).shape
        return rows, columns

    @property
    def bounds_m(self) -> tuple[float, float, float, float]:
        """Inclusive ``(x_min, x_max, y_min, y_max)`` map bounds."""
        rows, columns = self.shape
        x_min, y_min = self.origin_xy_m
        return (
            x_min,
            x_min + (columns - 1) * self.resolution_m,
            y_min,
            y_min + (rows - 1) * self.resolution_m,
        )

    def contains(self, points_xy_m: ArrayLike) -> bool:
        """Return whether every point lies inside the interpolation domain."""
        points = np.asarray(points_xy_m, dtype=float)
        if points.ndim == 1:
            points = points[None, :]
        if points.ndim != 2 or points.shape[1] != 2:
            raise ValueError("points_xy_m must have shape (N, 2)")
        x_min, x_max, y_min, y_max = self.bounds_m
        return bool(
            np.all((points[:, 0] >= x_min) & (points[:, 0] <= x_max))
            and np.all((points[:, 1] >= y_min) & (points[:, 1] <= y_max))
        )

    def sample(self, points_xy_m: ArrayLike) -> FloatArray:
        """Bilinearly sample positive-down depth at one or more points."""
        points = np.asarray(points_xy_m, dtype=float)
        scalar = points.ndim == 1
        if scalar:
            points = points[None, :]
        if points.ndim != 2 or points.shape[1] != 2 or not np.all(np.isfinite(points)):
            raise ValueError("points_xy_m must be finite with shape (N, 2)")
        if not self.contains(points):
            raise ValueError("bathymetry query lies outside map bounds")

        gx = (points[:, 0] - self.origin_xy_m[0]) / self.resolution_m
        gy = (points[:, 1] - self.origin_xy_m[1]) / self.resolution_m
        rows, columns = self.shape
        gx = np.clip(gx, 0.0, columns - 1.000000001)
        gy = np.clip(gy, 0.0, rows - 1.000000001)
        x0 = np.floor(gx).astype(int)
        y0 = np.floor(gy).astype(int)
        x1 = np.minimum(x0 + 1, columns - 1)
        y1 = np.minimum(y0 + 1, rows - 1)
        fx = gx - x0
        fy = gy - y0
        grid = cast(FloatArray, self.depth_grid_m)
        top = grid[y0, x0] * (1.0 - fx) + grid[y0, x1] * fx
        bottom = grid[y1, x0] * (1.0 - fx) + grid[y1, x1] * fx
        values = np.asarray(top * (1.0 - fy) + bottom * fy, dtype=np.float64)
        return values[0] if scalar else values


@dataclass(frozen=True)
class BathymetryProfile:
    """Bottom-depth samples at navigation-frame offsets from the vehicle."""

    offsets_xy_m: ArrayLike
    bottom_depth_m: ArrayLike
    variance_m2: float = 1.0
    timestamp_s: float | None = None

    def __post_init__(self) -> None:
        offsets = _readonly(self.offsets_xy_m, name="offsets_xy_m")
        depths = _readonly(self.bottom_depth_m, name="bottom_depth_m")
        if offsets.ndim != 2 or offsets.shape[1] != 2:
            raise ValueError("offsets_xy_m must have shape (N, 2)")
        if depths.shape != (offsets.shape[0],) or offsets.shape[0] < 3:
            raise ValueError("profile requires at least three depth samples")
        variance = _positive(self.variance_m2, name="variance_m2")
        timestamp = self.timestamp_s
        if timestamp is not None:
            timestamp = _positive(
                timestamp,
                name="timestamp_s",
                allow_zero=True,
            )
        object.__setattr__(self, "offsets_xy_m", offsets)
        object.__setattr__(self, "bottom_depth_m", depths)
        object.__setattr__(self, "variance_m2", variance)
        object.__setattr__(self, "timestamp_s", timestamp)

    @property
    def relief_m(self) -> float:
        """Peak-to-peak profile relief."""
        return float(np.ptp(cast(FloatArray, self.bottom_depth_m)))


@dataclass(frozen=True)
class TerrainMatcherConfig:
    """Search, ambiguity, and covariance settings for profile matching."""

    search_radius_m: float = 20.0
    grid_step_m: float = 2.0
    prior_weight: float = 0.25
    min_profile_relief_m: float = 0.75
    max_normalized_cost: float = 9.0
    min_cost_margin: float = 0.35
    ambiguity_separation_m: float = 5.0
    covariance_cost_window: float = 6.0
    remove_vertical_bias: bool = True

    def __post_init__(self) -> None:
        for name in (
            "search_radius_m",
            "grid_step_m",
            "max_normalized_cost",
            "ambiguity_separation_m",
            "covariance_cost_window",
        ):
            _positive(getattr(self, name), name=name)
        for name in ("prior_weight", "min_profile_relief_m", "min_cost_margin"):
            _positive(getattr(self, name), name=name, allow_zero=True)
        if not isinstance(self.remove_vertical_bias, bool):
            raise TypeError("remove_vertical_bias must be bool")


class MatchStatus(StrEnum):
    """Terrain matcher outcome."""

    ACCEPTED = "accepted"
    INSUFFICIENT_RELIEF = "insufficient_relief"
    OUT_OF_BOUNDS = "out_of_bounds"
    HIGH_RESIDUAL = "high_residual"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class BathymetryMatch:
    """Terrain matcher result and diagnostics."""

    status: MatchStatus
    measurement: BathymetryMeasurement | None = None
    best_cost: float | None = None
    cost_margin: float | None = None
    vertical_bias_m: float | None = None
    candidates_evaluated: int = 0

    @property
    def accepted(self) -> bool:
        """Return whether a fusion-ready fix was produced."""
        return self.status == MatchStatus.ACCEPTED and self.measurement is not None


class TerrainProfileMatcher:
    """Match a bottom profile to a bathymetry map around a navigation prior."""

    def __init__(
        self,
        bathymetry_map: BathymetryMap,
        cfg: TerrainMatcherConfig | None = None,
    ) -> None:
        if not isinstance(bathymetry_map, BathymetryMap):
            raise TypeError("bathymetry_map must be BathymetryMap")
        self.map = bathymetry_map
        self.cfg = cfg or TerrainMatcherConfig()

    def match(
        self,
        profile: BathymetryProfile,
        *,
        prior_pos: ArrayLike,
        prior_cov: ArrayLike,
    ) -> BathymetryMatch:
        """Return a quality-gated map fix for one bottom profile."""
        if profile.relief_m < self.cfg.min_profile_relief_m:
            return BathymetryMatch(MatchStatus.INSUFFICIENT_RELIEF)

        profile_offsets = cast(FloatArray, profile.offsets_xy_m)
        profile_depths = cast(FloatArray, profile.bottom_depth_m)
        prior = np.asarray(prior_pos, dtype=float)
        covariance = np.asarray(prior_cov, dtype=float)
        if prior.shape != (2,) or not np.all(np.isfinite(prior)):
            raise ValueError("prior_pos must be a finite 2-vector")
        if (
            covariance.shape != (2, 2)
            or not np.all(np.isfinite(covariance))
            or not np.allclose(covariance, covariance.T, atol=1e-10)
            or np.linalg.eigvalsh(covariance).min() < -1e-10
        ):
            raise ValueError("prior_cov must be finite, symmetric, and PSD")

        offsets = np.arange(
            -self.cfg.search_radius_m,
            self.cfg.search_radius_m + self.cfg.grid_step_m * 0.5,
            self.cfg.grid_step_m,
        )
        candidates: list[FloatArray] = []
        costs: list[float] = []
        biases: list[float] = []
        prior_inverse = np.linalg.pinv(
            covariance + np.eye(2) * max(self.cfg.grid_step_m**2 / 12.0, 1e-9)
        )

        for dx in offsets:
            for dy in offsets:
                candidate = prior + np.array([dx, dy])
                sample_points = candidate + profile_offsets
                if not self.map.contains(sample_points):
                    continue
                predicted = self.map.sample(sample_points)
                residual = predicted - profile_depths
                vertical_bias = (
                    float(np.mean(residual)) if self.cfg.remove_vertical_bias else 0.0
                )
                centered = residual - vertical_bias
                profile_cost = float(np.mean(centered**2 / profile.variance_m2))
                delta = candidate - prior
                prior_cost = float(delta @ prior_inverse @ delta)
                candidates.append(candidate)
                costs.append(profile_cost + self.cfg.prior_weight * prior_cost)
                biases.append(vertical_bias)

        if not candidates:
            return BathymetryMatch(MatchStatus.OUT_OF_BOUNDS)

        candidate_array = np.asarray(candidates)
        cost_array = np.asarray(costs)
        best_index = int(np.argmin(cost_array))
        best_position = candidate_array[best_index]
        best_cost = float(cost_array[best_index])
        best_bias = float(biases[best_index])
        if best_cost > self.cfg.max_normalized_cost:
            return BathymetryMatch(
                MatchStatus.HIGH_RESIDUAL,
                best_cost=best_cost,
                vertical_bias_m=best_bias,
                candidates_evaluated=len(candidates),
            )

        separated = (
            np.linalg.norm(candidate_array - best_position, axis=1)
            >= self.cfg.ambiguity_separation_m
        )
        separated[best_index] = False
        second_cost = (
            float(np.min(cost_array[separated])) if np.any(separated) else float("inf")
        )
        margin = second_cost - best_cost
        if margin < self.cfg.min_cost_margin:
            return BathymetryMatch(
                MatchStatus.AMBIGUOUS,
                best_cost=best_cost,
                cost_margin=margin,
                vertical_bias_m=best_bias,
                candidates_evaluated=len(candidates),
            )

        covariance_mask = cost_array <= best_cost + self.cfg.covariance_cost_window
        local_positions = candidate_array[covariance_mask]
        local_costs = cost_array[covariance_mask]
        weights = np.exp(-0.5 * (local_costs - best_cost))
        weights /= np.sum(weights)
        mean = np.sum(local_positions * weights[:, None], axis=0)
        deltas = local_positions - mean
        fix_covariance = (deltas * weights[:, None]).T @ deltas
        fix_covariance += np.eye(2) * self.cfg.grid_step_m**2 / 12.0
        fix_covariance = 0.5 * (fix_covariance + fix_covariance.T)

        measurement = BathymetryMeasurement(
            pos_fix=best_position,
            pos_cov=fix_covariance,
            timestamp_s=profile.timestamp_s,
        )
        return BathymetryMatch(
            MatchStatus.ACCEPTED,
            measurement=measurement,
            best_cost=best_cost,
            cost_margin=margin,
            vertical_bias_m=best_bias,
            candidates_evaluated=len(candidates),
        )


__all__ = [
    "BathymetryMap",
    "BathymetryMatch",
    "BathymetryProfile",
    "MatchStatus",
    "TerrainMatcherConfig",
    "TerrainProfileMatcher",
]
