"""TERCOM - Terrain Contour Matching.

Buffers a strip of measured ground elevations tagged with the navigator's
estimated sample positions, then searches a horizontal offset grid to best
correlate that measured profile against the stored DEM. The offset that
minimises mean-absolute-difference yields an absolute position fix.

The key assumption (same as fielded TERCOM/DSMAC systems): short-term INS
*relative* geometry of the strip is accurate, only the *absolute* offset has
drifted. So we solve for a single (dx, dy) shift.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np

from .. import estimation as est
from ..config import SimConfig
from ..terrain import Terrain


@dataclass
class TercomFix:
    pos: np.ndarray          # corrected position for latest sample [2]
    offset: np.ndarray       # applied (dx, dy) [m]
    cost: float              # residual MAD at best offset [m]
    cov: np.ndarray          # 2x2 position measurement covariance [m^2]
    valid: bool


class Tercom:
    def __init__(self, cfg: SimConfig, terrain: Terrain):
        self.cfg = cfg
        self.terrain = terrain
        self.buf: deque[tuple[np.ndarray, float]] = deque(maxlen=cfg.tercom_strip)

    def push(self, est_pos: np.ndarray, ground_elev: float) -> None:
        self.buf.append((np.asarray(est_pos, float).copy(), float(ground_elev)))

    def ready(self) -> bool:
        return len(self.buf) >= self.cfg.tercom_strip

    def correlate(self) -> TercomFix | None:
        if not self.ready():
            return None
        cfg = self.cfg
        pts = np.array([p for p, _ in self.buf])        # [S,2]
        meas = np.array([m for _, m in self.buf])       # [S]
        meas = meas - meas.mean()                       # remove baro/altitude bias

        offs = np.arange(-cfg.tercom_search, cfg.tercom_search + 1e-6,
                         cfg.tercom_search_step)
        cost = np.empty((offs.size, offs.size))
        for i, dx in enumerate(offs):
            for j, dy in enumerate(offs):
                elev = self.terrain.elevation(pts[:, 0] + dx, pts[:, 1] + dy)
                elev = elev - elev.mean()
                cost[i, j] = np.mean(np.abs(elev - meas))

        i0, j0 = np.unravel_index(np.argmin(cost), cost.shape)
        if not self._peak_is_distinct(cost, i0, j0):
            return TercomFix(pos=pts[-1].copy(), offset=np.zeros(2),
                             cost=float(cost[i0, j0]), cov=np.eye(2) * 1e9,
                             valid=False)
        dx, dy = self._subcell(offs, cost, i0, j0)
        fix = pts[-1] + np.array([dx, dy])

        # Covariance from local curvature of the correlation surface.
        cov = self._cov_from_surface(offs, cost, i0, j0)
        return TercomFix(pos=fix, offset=np.array([dx, dy]),
                         cost=float(cost[i0, j0]), cov=cov, valid=True)

    def _peak_is_distinct(self, cost: np.ndarray, i0: int, j0: int) -> bool:
        """Reject flat or multi-peak correlation surfaces."""
        best = float(cost[i0, j0])
        if best <= self.cfg.tercom_min_cost_margin:
            return True
        mask = np.ones(cost.shape, dtype=bool)
        i1, i2 = max(0, i0 - 1), min(cost.shape[0], i0 + 2)
        j1, j2 = max(0, j0 - 1), min(cost.shape[1], j0 + 2)
        mask[i1:i2, j1:j2] = False
        if not np.any(mask):
            return True
        second = float(np.min(cost[mask]))
        return (second - best) >= self.cfg.tercom_min_cost_margin

    @staticmethod
    def _subcell(offs, cost, i0, j0):
        def parab(c_m, c_0, c_p, step, center):
            denom = c_m - 2 * c_0 + c_p
            if abs(denom) < 1e-9:
                return center
            return center - 0.5 * step * (c_p - c_m) / denom
        step = offs[1] - offs[0]
        dx = offs[i0]
        dy = offs[j0]
        if 0 < i0 < offs.size - 1:
            dx = parab(cost[i0 - 1, j0], cost[i0, j0], cost[i0 + 1, j0], step, offs[i0])
        if 0 < j0 < offs.size - 1:
            dy = parab(cost[i0, j0 - 1], cost[i0, j0], cost[i0, j0 + 1], step, offs[j0])
        return dx, dy

    def _cov_from_surface(self, offs, cost, i0, j0):
        step = offs[1] - offs[0]
        base = self.cfg.tercom_search_step
        cxx = cyy = base ** 2
        if 0 < i0 < offs.size - 1:
            d2 = cost[i0 - 1, j0] - 2 * cost[i0, j0] + cost[i0 + 1, j0]
            if d2 > 1e-6:
                cxx = max((step ** 2) * self._noise() / d2, base ** 2 * 0.25)
        if 0 < j0 < offs.size - 1:
            d2 = cost[i0, j0 - 1] - 2 * cost[i0, j0] + cost[i0, j0 + 1]
            if d2 > 1e-6:
                cyy = max((step ** 2) * self._noise() / d2, base ** 2 * 0.25)
        return np.diag([cxx, cyy])

    def _noise(self) -> float:
        return est.terrain_meas_var(self.cfg)
