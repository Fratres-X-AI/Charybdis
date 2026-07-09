"""Synthetic Digital Elevation Model (DEM) with bilinear query and gradient.

Represents the stored terrain map the interceptor carries on-board and the
"real" ground it flies over. Elevation is a function of local ENU (x, y).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import SimConfig


@dataclass
class Terrain:
    grid: np.ndarray          # elevation [ny, nx] metres
    res: float                # grid spacing [m]
    origin: tuple[float, float] = (0.0, 0.0)

    @property
    def size(self) -> float:
        return (self.grid.shape[0] - 1) * self.res

    @classmethod
    def synthetic(cls, cfg: SimConfig) -> Terrain:
        """Build fractal-like terrain: layered sinusoids plus gaussian hills."""
        rng = np.random.default_rng(cfg.seed)
        n = int(cfg.terrain_size / cfg.terrain_res) + 1
        xs = np.linspace(0.0, cfg.terrain_size, n)
        ys = np.linspace(0.0, cfg.terrain_size, n)
        gx, gy = np.meshgrid(xs, ys)
        z = np.zeros_like(gx)

        # Layered ridges (fractal sum) for broad, correlatable relief.
        for k in range(1, 7):
            fx = rng.uniform(0.4, 1.6) * k / cfg.terrain_size
            fy = rng.uniform(0.4, 1.6) * k / cfg.terrain_size
            ph = rng.uniform(0.0, 2 * np.pi, 2)
            amp = cfg.terrain_relief / (k ** 1.35)
            z += amp * np.sin(2 * np.pi * fx * gx + ph[0]) * np.cos(
                2 * np.pi * fy * gy + ph[1]
            )

        # Scattered peaks / basins for local distinctiveness.
        for _ in range(38):
            cx, cy = rng.uniform(0, cfg.terrain_size, 2)
            sig = rng.uniform(600.0, 2600.0)
            amp = rng.uniform(-1.0, 1.0) * cfg.terrain_relief * 0.7
            z += amp * np.exp(-(((gx - cx) ** 2 + (gy - cy) ** 2) / (2 * sig ** 2)))

        z -= z.min()  # elevations >= 0
        return cls(grid=z.astype(np.float64), res=cfg.terrain_res)

    def _to_grid(self, x: float, y: float) -> tuple[float, float]:
        return (x - self.origin[0]) / self.res, (y - self.origin[1]) / self.res

    def elevation(self, x, y):
        """Bilinear-interpolated elevation at world coords (vectorised)."""
        x = np.asarray(x, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        gx, gy = self._to_grid(x, y)
        ny, nx = self.grid.shape
        gx = np.clip(gx, 0, nx - 1.001)
        gy = np.clip(gy, 0, ny - 1.001)
        x0 = np.floor(gx).astype(int)
        y0 = np.floor(gy).astype(int)
        x1, y1 = x0 + 1, y0 + 1
        fx, fy = gx - x0, gy - y0
        g = self.grid
        top = g[y0, x0] * (1 - fx) + g[y0, x1] * fx
        bot = g[y1, x0] * (1 - fx) + g[y1, x1] * fx
        return top * (1 - fy) + bot * fy

    def gradient(self, x: float, y: float, h: float | None = None) -> np.ndarray:
        """Central-difference terrain slope [dz/dx, dz/dy] at (x, y)."""
        h = h if h is not None else self.res
        dzdx = (self.elevation(x + h, y) - self.elevation(x - h, y)) / (2 * h)
        dzdy = (self.elevation(x, y + h) - self.elevation(x, y - h)) / (2 * h)
        return np.array([float(dzdx), float(dzdy)])
