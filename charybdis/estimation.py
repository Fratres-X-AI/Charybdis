"""Shared estimation math for the Charybdis navigation filters.

This module collects the cross-cutting techniques the EKF and particle filter
rely on, so their behaviour is identical, auditable and tuned in one place:

* **Measurement / map-uncertainty budget** - the terrain-elevation measurement
  variance is *not* just the sensor noise. The stored bathymetric map has its
  own vertical error, the map is only sampled on a grid (bilinear interpolation
  error), and - for a filter that *linearises* the map (the EKF) - the local
  plane does not explain the terrain over the whole position-uncertainty region.
  :func:`terrain_meas_var` and :func:`stochastic_linearize` account for these.

* **Statistical / unscented linearisation** - instead of the point-slope
  Jacobian (which is inaccurate exactly when the position error is large, the
  regime where the EKF diverges), :func:`stochastic_linearize` fits a plane to
  DEM samples drawn over the position prior and returns both the averaged slope
  *and* the residual variance the EKF must add to stay consistent.

* **Innovation-adaptive process noise** (:class:`InnovationMonitor`) - covariance
  matching / IAE: when innovations run larger than the filter predicts, the
  process noise is scaled up so the covariance keeps up with reality.

* **Consistency + fusion primitives** - :func:`nees`, :func:`covariance_intersection`
  (consistent fusion under unknown cross-correlation), and PF ambiguity
  detectors used by the mode-management layer.

References
----------
- Bar-Shalom, Li & Kirubarajan, *Estimation with Applications to Tracking and
  Navigation* (2001) - NEES/NIS consistency, covariance matching.
- Mehra (1970); Mohamed & Schwarz (1999) - innovation adaptive estimation.
- Julier & Uhlmann (1997) - unscented transform; covariance intersection.
- Han, Kim & Kim (2013) - stochastic linearisation for terrain-referenced nav.
- Bergman (1999); Anonsen & Hallingstad (2006) - point-mass TRN, terrain info.
"""

from __future__ import annotations

from collections import deque

import numpy as np


# --------------------------------------------------------------------------- #
#  Measurement / map-uncertainty budget
# --------------------------------------------------------------------------- #
def sensor_elev_var(cfg) -> float:
    """Raw altimeter-chain elevation variance [m^2] (radar AGL + baro MSL)."""
    return cfg.radar_noise**2 + cfg.baro_noise**2


def terrain_meas_var(cfg, slope: float | None = None) -> float:
    """Terrain-elevation measurement variance [m^2] used by non-linear filters
    such as the particle filter, which evaluate the DEM directly and so need no
    EKF linearisation term.

    ``R = sensor + map_error + interpolation_error``:

    * ``sensor``            - altimeter chain (radar AGL + baro MSL),
    * ``map_error``         - vertical uncertainty of the stored bathymetry
      (``cfg.map_sigma``); the map is **not** ground truth,
    * ``interpolation``     - the DEM is only known at grid nodes, so the value
      between nodes is uncertain by roughly ``frac * cell * |slope|``.
    """
    R = sensor_elev_var(cfg) + cfg.map_sigma**2
    if slope is not None and getattr(cfg, "map_interp_frac", 0.0) > 0.0:
        R += (cfg.map_interp_frac * cfg.terrain_res * float(abs(slope))) ** 2
    return float(R)


def _sigma_points(mean: np.ndarray, cov: np.ndarray, kappa: float):
    """Symmetric unscented sigma points and weights for a 2-D Gaussian."""
    n = mean.size
    c = 0.5 * (cov + cov.T)
    try:
        S = np.linalg.cholesky((n + kappa) * c)
    except np.linalg.LinAlgError:
        w, V = np.linalg.eigh((n + kappa) * c)
        S = V @ np.diag(np.sqrt(np.clip(w, 0.0, None)))
    pts = [mean]
    for i in range(n):
        pts.append(mean + S[:, i])
        pts.append(mean - S[:, i])
    wm = np.full(2 * n + 1, 1.0 / (2.0 * (n + kappa)))
    wm[0] = kappa / (n + kappa)
    return np.array(pts), wm


def stochastic_linearize(terrain, pos, P_pos, cfg):
    """Statistical (unscented) linearisation of the DEM over a position prior.

    Draws sigma points from ``N(pos, P_pos)`` (eigenvalue-clipped so the
    neighbourhood is always terrain-informative but never absurdly wide),
    evaluates the DEM at each, and fits a weighted plane ``z = h0 + g . delta``.

    Returns ``(h0, gradient[2], R_lin)`` where ``h0`` is the prior-averaged
    predicted elevation, ``gradient`` is the averaged slope (a far more stable
    EKF Jacobian than the point derivative when the position error is large) and
    ``R_lin`` is the weighted residual variance the plane fails to explain - the
    linearisation error that must be added to the measurement noise to keep the
    EKF consistent (Han et al. 2013).
    """
    pos = np.asarray(pos, float)
    res = float(cfg.terrain_res)
    lo = (max(cfg.ekf_sl_min_frac, 0.1) * res) ** 2
    hi = float(cfg.ekf_sl_max_radius) ** 2
    w_e, V = np.linalg.eigh(0.5 * (P_pos + P_pos.T))
    w_e = np.clip(w_e, lo, hi)
    Pc = V @ np.diag(w_e) @ V.T

    pts, wm = _sigma_points(pos, Pc, cfg.ekf_sl_kappa)
    z = terrain.elevation(pts[:, 0], pts[:, 1])
    d = pts - pos  # offsets about the mean
    A = np.column_stack([np.ones(len(pts)), d[:, 0], d[:, 1]])
    W = np.diag(wm)
    try:
        beta = np.linalg.solve(A.T @ W @ A, A.T @ W @ z)
    except np.linalg.LinAlgError:
        beta, *_ = np.linalg.lstsq(np.sqrt(W) @ A, np.sqrt(W) @ z, rcond=None)
    h0 = float(beta[0])
    grad = np.array([beta[1], beta[2]], float)
    resid = z - A @ beta
    R_lin = float(np.sum(wm * resid**2))
    return h0, grad, R_lin


# --------------------------------------------------------------------------- #
#  Innovation-adaptive process noise (covariance matching / IAE)
# --------------------------------------------------------------------------- #
class InnovationMonitor:
    """Sliding-window monitor of normalised innovation squared (NIS).

    Feeds two behaviours: (a) an adaptive **process-noise scale** that grows
    when innovations run larger than the filter predicts (its covariance is too
    tight for reality), and (b) a **fault flag** when that mismatch is large and
    sustained - the signal the coordinator uses to declare the EKF diverged.
    """

    def __init__(self, window: int, dof: int = 1):
        self.window = int(window)
        self.dof = int(dof)
        self.buf: deque[float] = deque(maxlen=self.window)
        self._scale = 1.0

    def push(self, nis: float) -> None:
        if np.isfinite(nis):
            self.buf.append(float(nis))

    def __len__(self) -> int:
        return len(self.buf)

    @property
    def mean_nis(self) -> float:
        return float(np.mean(self.buf)) if self.buf else float(self.dof)

    def ratio(self) -> float:
        """Empirical / expected NIS (1.0 == perfectly consistent)."""
        return self.mean_nis / max(self.dof, 1)

    def q_scale(self, lo: float, hi: float, min_count: int, ema: float = 0.2) -> float:
        """EMA-smoothed multiplicative process-noise scale, clamped to [lo, hi]."""
        if len(self.buf) < min_count:
            target = 1.0
        else:
            target = float(np.clip(self.ratio(), lo, hi))
        self._scale += ema * (target - self._scale)
        return float(np.clip(self._scale, lo, hi))

    def faulted(self, ratio_thresh: float, min_count: int) -> bool:
        return len(self.buf) >= min_count and self.ratio() > ratio_thresh


# --------------------------------------------------------------------------- #
#  Consistency + fusion primitives
# --------------------------------------------------------------------------- #
def safe_inv(P: np.ndarray) -> np.ndarray:
    try:
        return np.linalg.inv(P)
    except np.linalg.LinAlgError:
        return np.linalg.pinv(P)


def nees(err: np.ndarray, P: np.ndarray) -> float:
    """Normalised estimation error squared ``e' P^-1 e`` (needs truth error)."""
    e = np.asarray(err, float)
    return float(e @ safe_inv(P) @ e)


def mahalanobis2(delta: np.ndarray, cov: np.ndarray) -> float:
    d = np.asarray(delta, float)
    return float(d @ safe_inv(cov) @ d)


def covariance_intersection(xa, Pa, xb, Pb, omega: float | None = None):
    """Consistent fusion of two estimates with *unknown* cross-correlation.

    CI is useful for EKF/PF agreement checks because both filters share the same
    IMU prediction, so their errors are correlated by an unknown amount and
    naive fusion would be over-confident. ``omega`` is chosen to minimise the
    fused covariance trace when not supplied.
    """
    xa = np.asarray(xa, float)
    xb = np.asarray(xb, float)
    Pai = safe_inv(Pa)
    Pbi = safe_inv(Pb)
    if omega is None:
        best = None
        for w in np.linspace(0.05, 0.95, 19):
            Pf = safe_inv(w * Pai + (1.0 - w) * Pbi)
            tr = float(np.trace(Pf))
            if best is None or tr < best[0]:
                best = (tr, float(w))
        omega = best[1]
    Pi = omega * Pai + (1.0 - omega) * Pbi
    P = safe_inv(Pi)
    x = P @ (omega * Pai @ xa + (1.0 - omega) * Pbi @ xb)
    return x, P, float(omega)


# --------------------------------------------------------------------------- #
#  Terrain-ambiguity / multi-hypothesis detection
# --------------------------------------------------------------------------- #
def cluster_modes(
    pos: np.ndarray, w: np.ndarray, radius: float, top: int = 400
) -> list[tuple[np.ndarray, float]]:
    """Greedy weighted clustering of a particle cloud into spatial modes.

    Only the ``top`` heaviest particles are clustered (cheap and robust);
    returns ``[(center, weight), ...]`` sorted by descending weight.
    """
    n = len(w)
    if n == 0:
        return []
    order = np.argsort(w)[::-1][: min(top, n)]
    r2 = radius * radius
    centers: list[np.ndarray] = []
    masses: list[float] = []
    sums: list[np.ndarray] = []
    for i in order:
        p = pos[i]
        placed = False
        for k, c in enumerate(centers):
            dx = p - c
            if dx[0] * dx[0] + dx[1] * dx[1] <= r2:
                masses[k] += w[i]
                sums[k] += w[i] * p
                centers[k] = sums[k] / masses[k]
                placed = True
                break
        if not placed:
            centers.append(p.copy())
            masses.append(float(w[i]))
            sums.append(w[i] * p.copy())
    modes = sorted(zip(centers, masses, strict=True), key=lambda m: m[1], reverse=True)
    return modes


def mode_count(modes: list[tuple[np.ndarray, float]], frac: float) -> int:
    """Number of modes carrying at least ``frac`` of the clustered mass."""
    if not modes:
        return 0
    total = sum(m for _, m in modes)
    if total <= 0:
        return 0
    return int(sum(1 for _, m in modes if m / total >= frac))


def grid_multimodality(p: np.ndarray, frac: float = 0.4) -> tuple[int, float]:
    """Count significant peaks of a 2-D probability grid (point-mass filter).

    Returns ``(n_modes, secondary_mass_fraction)``. A unimodal posterior has one
    peak and ~0 secondary mass; competing terrain hypotheses show up as extra
    peaks holding a non-trivial mass fraction. Uses a cheap 4-connected flood
    fill over cells above ``frac * peak``.
    """
    pk = float(p.max())
    if pk <= 0.0:
        return 0, 0.0
    mask = p >= frac * pk
    ny, nx = p.shape
    seen = np.zeros_like(mask, dtype=bool)
    comp_mass: list[float] = []
    for j in range(ny):
        for i in range(nx):
            if not mask[j, i] or seen[j, i]:
                continue
            stack = [(j, i)]
            seen[j, i] = True
            m = 0.0
            while stack:
                cj, ci = stack.pop()
                m += float(p[cj, ci])
                for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nj, ni = cj + dj, ci + di
                    if (
                        0 <= nj < ny
                        and 0 <= ni < nx
                        and mask[nj, ni]
                        and not seen[nj, ni]
                    ):
                        seen[nj, ni] = True
                        stack.append((nj, ni))
            comp_mass.append(m)
    if not comp_mass:
        return 0, 0.0
    comp_mass.sort(reverse=True)
    total = sum(comp_mass)
    secondary = (total - comp_mass[0]) / total if total > 0 else 0.0
    return len(comp_mass), float(secondary)
