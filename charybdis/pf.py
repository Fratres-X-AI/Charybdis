"""Terrain-aided particle filter (bootstrap SIR) for GPS-denied navigation.

Why a particle filter for terrain nav? The terrain-elevation measurement
``z = DEM(px, py) + noise`` is a strongly non-linear, multi-modal function of
horizontal position: many locations share a similar elevation, so the position
posterior is non-Gaussian and often multi-hypothesis. An EKF linearises the
DEM about a single estimate and can lock onto the wrong local minimum when the
prior error is large. A particle filter represents the full posterior with a
weighted sample set and stays consistent through the ambiguity, resolving it as
the vehicle flies over increasingly distinctive terrain.

Particle state matches the EKF:  [px, py, vx, vy, bax, bay].
IMU specific force drives prediction; the radar/baro terrain reading drives the
measurement update via the true (non-linearised) elevation likelihood.
"""
from __future__ import annotations

import numpy as np

from .config import SimConfig
from .terrain import Terrain

D = 6  # particle state dimension


class TerrainParticleFilter:
    def __init__(self, cfg: SimConfig, terrain: Terrain, pos0, vel0,
                 rng: np.random.Generator | None = None):
        self.cfg = cfg
        self.terrain = terrain
        self.rng = rng or np.random.default_rng(cfg.seed + 202)
        n = cfg.n_particles
        self.N = n
        self.X = np.zeros((n, D))
        self.X[:, 0:2] = np.asarray(pos0) + self.rng.normal(0, cfg.init_pos_std, (n, 2))
        self.X[:, 2:4] = np.asarray(vel0) + self.rng.normal(0, cfg.init_vel_std, (n, 2))
        self.X[:, 4:6] = self.rng.normal(0, cfg.accel_bias0, (n, 2))
        self.w = np.full(n, 1.0 / n)
        self._R = cfg.radar_noise ** 2 + cfg.baro_noise ** 2
        self._last_fix_pos: np.ndarray | None = None
        self._last_fix_t: float | None = None

    # ---- prediction (IMU driven) --------------------------------------- #
    def predict(self, accel_meas: np.ndarray, dt: float) -> None:
        cfg = self.cfg
        accel_meas = np.asarray(accel_meas, float)
        sigma_a = cfg.accel_noise / np.sqrt(dt)
        a = accel_meas[None, :] - self.X[:, 4:6]
        a = a + self.rng.normal(0.0, sigma_a, (self.N, 2))
        self.X[:, 0:2] += self.X[:, 2:4] * dt + 0.5 * a * dt * dt
        self.X[:, 2:4] += a * dt
        self.X[:, 4:6] += self.rng.normal(0.0, cfg.accel_bias_rw * np.sqrt(dt),
                                          (self.N, 2))

    # ---- measurement updates ------------------------------------------- #
    def update_trn(self, ground_elev_meas: float) -> None:
        elev = self.terrain.elevation(self.X[:, 0], self.X[:, 1])
        innov = ground_elev_meas - elev
        logw = np.log(self.w + 1e-300) - 0.5 * innov * innov / self._R
        self._set_weights(logw)
        self._maybe_resample()

    def update_position(self, pos_fix: np.ndarray, cov: np.ndarray,
                        t: float | None = None) -> None:
        """Absolute TERCOM position fix.

        Steps: (1) *gate* the fix with a Mahalanobis test against the current
        cloud (cov + cloud covariance) - the PF analogue of the EKF chi-square
        gate - so an outlier fix cannot corrupt an already-accurate cloud, yet a
        genuinely lost cloud (wide spread) still accepts a relocalising fix;
        (2) importance-reweight by the fix likelihood; and (3) inject a fraction
        of particles at the fix to relocalise where the cloud has no samples.

        Injected *velocity* is estimated by differencing consecutive accepted
        fixes (two absolute positions => velocity), which corrects the otherwise
        weakly-observable velocity/bias drift that position-only fixes cannot.
        The injection covariance is eigenvalue-clipped since the raw correlation
        covariance can be enormous along an ambiguous along-track axis.
        """
        pos_fix = np.asarray(pos_fix, float)
        cov = np.asarray(cov, float)

        innov = pos_fix - self.pos
        S = cov + self.pos_cov()
        if float(innov @ np.linalg.inv(S) @ innov) > self.cfg.gate_chi2:
            return                                       # reject outlier fix

        Rinv = np.linalg.inv(cov)
        d = self.X[:, 0:2] - pos_fix
        md = np.einsum("ni,ij,nj->n", d, Rinv, d)
        self._set_weights(np.log(self.w + 1e-300) - 0.5 * md)
        self._maybe_resample()

        w_eig, V = np.linalg.eigh(cov)
        fix_std = float(np.sqrt(max(w_eig.max(), 0.0)))
        m = int(self.cfg.pf_inject * self.N)
        if m > 0 and fix_std <= self.cfg.pf_inject_std_max:
            if self._last_fix_pos is not None and t is not None \
                    and t > self._last_fix_t:
                v_inj = (pos_fix - self._last_fix_pos) / (t - self._last_fix_t)
            else:
                v_inj = self.vel
            lo = (0.5 * self.cfg.tercom_search_step) ** 2
            hi = self.cfg.pf_inject_std_max ** 2
            cov_inj = V @ np.diag(np.clip(w_eig, lo, hi)) @ V.T
            L = np.linalg.cholesky(cov_inj + 1e-6 * np.eye(2))
            sel = np.argsort(self.w)[:m]                 # replace weakest
            self.X[sel, 0:2] = pos_fix + self.rng.normal(0, 1, (m, 2)) @ L.T
            self.X[sel, 2:4] = v_inj + self.rng.normal(
                0, self.cfg.init_vel_std * 0.5, (m, 2))
            self.w[sel] = 1.0 / self.N
            self.w /= self.w.sum()

        if t is not None:
            self._last_fix_pos = pos_fix.copy()
            self._last_fix_t = t

    def _set_weights(self, logw: np.ndarray) -> None:
        logw -= logw.max()
        w = np.exp(logw)
        s = w.sum()
        self.w = w / s if s > 0 else np.full(self.N, 1.0 / self.N)

    def _maybe_resample(self) -> None:
        if self.neff() < self.cfg.pf_neff_frac * self.N:
            self._resample()

    # ---- resampling + roughening --------------------------------------- #
    def neff(self) -> float:
        return float(1.0 / np.sum(self.w ** 2))

    def _resample(self) -> None:
        n = self.N
        positions = (self.rng.random() + np.arange(n)) / n
        idx = np.searchsorted(np.cumsum(self.w), positions)
        idx = np.clip(idx, 0, n - 1)
        self.X = self.X[idx].copy()
        self.w = np.full(n, 1.0 / n)
        # Roughening with absolute floors: without a floor the jitter scales with
        # the (collapsed) spread and cannot re-expand a degenerate cloud, leaving
        # the filter confidently wrong and blind to terrain. The floors keep the
        # cloud wide enough that the elevation measurement stays informative.
        std = self.X.std(axis=0)
        sigma = self.cfg.pf_roughen * std * n ** (-1.0 / D)
        sigma[0:2] = np.maximum(sigma[0:2], self.cfg.pf_pos_floor)
        sigma[2:4] = np.maximum(sigma[2:4], self.cfg.pf_vel_floor)
        self.X += self.rng.normal(0.0, 1.0, (n, D)) * sigma[None, :]

    # ---- estimates ----------------------------------------------------- #
    @property
    def pos(self) -> np.ndarray:
        return self.w @ self.X[:, 0:2]

    @property
    def vel(self) -> np.ndarray:
        return self.w @ self.X[:, 2:4]

    def pos_cov(self) -> np.ndarray:
        mu = self.pos
        d = self.X[:, 0:2] - mu
        return (d * self.w[:, None]).T @ d

    @property
    def pos_std(self) -> np.ndarray:
        return np.sqrt(np.clip(np.diag(self.pos_cov()), 0.0, None))
