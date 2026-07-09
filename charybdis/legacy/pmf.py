"""Marginalized Point-Mass Filter (PMF) for terrain-aided navigation.

Why a point-mass filter? The fielded state of the art for terrain-referenced
navigation (Bergman 1997; Anonsen & Hallingstad, HUGIN/FFI) represents the
position posterior as probability mass on a grid and evaluates the terrain
likelihood *without linearising* the DEM, so it stays consistent through the
multi-modal ambiguity of self-similar terrain where an EKF can lock onto the
wrong local minimum. After convergence a grid filter approaches the Cramer-Rao
bound.

This is a *marginalized* (Rao-Blackwellised) PMF. The strongly non-linear
horizontal position is handled by the grid; the near-linear velocity and
accelerometer-bias states are carried in a Kalman backbone and updated
analytically from the grid's position correction via the prior cross-covariance:

    l | pos ~ N( l⁻ + J·(pos − p⁻),  ... ),   J = Pₚₚ⁻¹·Pₚₗ

Each terrain cycle the grid is seeded from the backbone's Gaussian position
prior, multiplied by a heavy-tailed **Student-t** terrain-elevation likelihood
(dof ``pmf_meas_dof``) that down-weights sonar/altimeter gross errors (the
robust-estimation idea from recent outlier-robust TAN work), and renormalised.
The grid posterior (mean, covariance) replaces the position marginal; the
velocity/bias states and all cross-covariances follow by the law of total
covariance. Because the update weights the position correction by the grid
covariance, the weakly-observable along-track direction is naturally trusted
less, which keeps velocity/bias estimation stable.
"""
from __future__ import annotations

import numpy as np

from .. import estimation as est
from ..config import SimConfig
from ..terrain import Terrain


class TerrainPointMassFilter:
    N = 6  # backbone state [px, py, vx, vy, bax, bay]

    def __init__(self, cfg: SimConfig, terrain: Terrain, pos0, vel0):
        self.cfg = cfg
        self.terrain = terrain
        self.res = float(cfg.pmf_res)

        self.x = np.zeros(self.N)
        self.x[0:2] = pos0
        self.x[2:4] = vel0
        p = np.zeros(self.N)
        p[0:2] = cfg.init_pos_std ** 2
        p[2:4] = cfg.init_vel_std ** 2
        p[4:6] = cfg.accel_bias0 ** 2
        self.P = np.diag(p)

        # Grid of position offsets [m] around the backbone position estimate.
        half = max(cfg.pmf_halfwidth, 3.0 * cfg.init_pos_std)
        n = int(round(half / self.res))
        self.axis = np.arange(-n, n + 1) * self.res
        self.G = self.axis.size
        self.OX, self.OY = np.meshgrid(self.axis, self.axis)   # (G,G); OX->cols
        self.p = np.full((self.G, self.G), 1.0 / (self.G * self.G))

        # Terrain-match noise inflated over raw sensor noise to account for DEM
        # interpolation error and terrain non-linearity (keeps the filter
        # consistent - a valid posterior stays no wider than the prior), plus an
        # explicit stored-map vertical error term (the bathymetry is not ground
        # truth).
        self._R = (cfg.pmf_meas_infl * est.sensor_elev_var(cfg)
                   + cfg.map_sigma ** 2)
        self._cov_floor = (0.35 * self.res) ** 2

    # ---- prediction (IMU driven, same model as the EKF) ---------------- #
    def predict(self, accel_meas: np.ndarray, dt: float) -> None:
        cfg = self.cfg
        b = self.x[4:6]
        a = np.asarray(accel_meas, float) - b
        self.x[0:2] += self.x[2:4] * dt + 0.5 * a * dt * dt
        self.x[2:4] += a * dt

        F = np.eye(self.N)
        F[0:2, 2:4] = np.eye(2) * dt
        F[0:2, 4:6] = -0.5 * dt * dt * np.eye(2)
        F[2:4, 4:6] = -dt * np.eye(2)

        q_a = cfg.accel_noise ** 2 * cfg.pmf_process_infl * self._q_scale()
        q_b = cfg.accel_bias_rw ** 2
        Q = np.zeros((self.N, self.N))
        for i in range(2):
            Q[i, i] = q_a * dt ** 3 / 3.0
            Q[i, i + 2] = Q[i + 2, i] = q_a * dt ** 2 / 2.0
            Q[i + 2, i + 2] = q_a * dt
            Q[i + 4, i + 4] = q_b * dt
        self.P = F @ self.P @ F.T + Q

    def _q_scale(self) -> float:
        """Terrain-driven process inflation: in low-information terrain the grid
        update barely moves, so extra process noise keeps the posterior from
        becoming over-confident before distinctive terrain returns."""
        cfg = self.cfg
        if not cfg.adapt_q_terrain:
            return 1.0
        grad = self.terrain.gradient(self.x[0], self.x[1])
        info = float(grad @ grad)
        ref = cfg.adapt_q_terrain_ref ** 2
        factor = 1.0 + (cfg.adapt_q_terrain_max - 1.0) / (1.0 + info / max(ref, 1e-9))
        return float(np.clip(factor, 1.0, cfg.adapt_q_terrain_max))

    # ---- terrain update (non-linear grid + marginalized linear states) - #
    def update_trn(self, ground_elev_meas: float, t: float | None = None) -> None:
        p_minus = self.x[0:2].copy()
        Ppp = self.P[0:2, 0:2]
        try:
            Pinv = np.linalg.inv(Ppp)
        except np.linalg.LinAlgError:
            Pinv = np.linalg.pinv(Ppp)

        # Gaussian position prior on the offset grid.
        dx, dy = self.OX, self.OY
        quad = Pinv[0, 0] * dx * dx + 2 * Pinv[0, 1] * dx * dy + Pinv[1, 1] * dy * dy
        log_prior = -0.5 * quad

        # Robust (Student-t) terrain-elevation likelihood.
        dem = self.terrain.elevation(p_minus[0] + dx, p_minus[1] + dy)
        innov = float(ground_elev_meas) - dem
        nu = self.cfg.pmf_meas_dof
        if np.isfinite(nu):
            log_lik = -0.5 * (nu + 1.0) * np.log1p((innov * innov) / (nu * self._R))
        else:
            log_lik = -0.5 * innov * innov / self._R

        logp = log_prior + log_lik
        logp -= logp.max()
        g = np.exp(logp)
        s = g.sum()
        if s <= 0 or not np.isfinite(s):
            return
        g /= s
        self.p = g

        # Grid posterior moments (position marginal).
        mx = float(np.sum(g * dx))
        my = float(np.sum(g * dy))
        cxx = float(np.sum(g * (dx - mx) ** 2)) + self._cov_floor
        cyy = float(np.sum(g * (dy - my) ** 2)) + self._cov_floor
        cxy = float(np.sum(g * (dx - mx) * (dy - my)))
        g_pos = p_minus + np.array([mx, my])
        g_cov = np.array([[cxx, cxy], [cxy, cyy]])

        self._impose_position(g_pos, g_cov, Pinv)

    def _impose_position(self, g_pos, g_cov, Pinv) -> None:
        """Replace the position marginal with (g_pos, g_cov); propagate to the
        velocity/bias states through the prior cross-covariance (marginalized
        Rao-Blackwellised update / law of total covariance)."""
        Ppl = self.P[0:2, 2:6]                 # 2x4 position<->linear cross-cov
        J = Pinv @ Ppl                         # 2x4
        dpos = g_pos - self.x[0:2]

        self.x[2:6] = self.x[2:6] + J.T @ dpos
        self.x[0:2] = g_pos

        Pll = self.P[2:6, 2:6]
        Pll_post = Pll - Ppl.T @ Pinv @ Ppl + J.T @ g_cov @ J
        Ppl_post = g_cov @ J

        self.P[0:2, 0:2] = g_cov
        self.P[2:6, 2:6] = Pll_post
        self.P[0:2, 2:6] = Ppl_post
        self.P[2:6, 0:2] = Ppl_post.T
        self.P = 0.5 * (self.P + self.P.T)

    # ---- TERCOM position fix (linear Gaussian update) ------------------ #
    def update_position(self, pos_fix: np.ndarray, cov: np.ndarray,
                        t: float | None = None) -> None:
        H = np.zeros((2, self.N))
        H[0, 0] = H[1, 1] = 1.0
        R = np.asarray(cov, float)
        y = np.asarray(pos_fix, float) - self.x[0:2]
        S = H @ self.P @ H.T + R
        Si = np.linalg.inv(S)
        if float(y @ Si @ y) > self.cfg.gate_chi2:
            return
        K = self.P @ H.T @ Si
        self.x = self.x + K @ y
        A = np.eye(self.N) - K @ H
        self.P = A @ self.P @ A.T + K @ R @ K.T
        self.P = 0.5 * (self.P + self.P.T)

    # ---- mode / ambiguity awareness ------------------------------------ #
    def multimodality(self) -> tuple[int, float]:
        """(n_significant_peaks, secondary_mass_fraction) of the grid posterior."""
        return est.grid_multimodality(self.p, self.cfg.mode_grid_frac)

    def n_modes(self) -> int:
        return self.multimodality()[0]

    # ---- estimates ----------------------------------------------------- #
    @property
    def pos(self) -> np.ndarray:
        return self.x[0:2].copy()

    @property
    def vel(self) -> np.ndarray:
        return self.x[2:4].copy()

    def pos_cov(self) -> np.ndarray:
        return self.P[0:2, 0:2].copy()

    @property
    def pos_std(self) -> np.ndarray:
        return np.sqrt(np.clip(np.diag(self.P)[0:2], 0.0, None))
