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

Prime-level features:
  * **Map-uncertainty aware, heteroscedastic likelihood** - each particle's
    elevation-match variance includes the stored-map error and a slope-projected
    interpolation term, so particles over steep terrain (where the map is least
    trustworthy) are down-weighted correctly.
  * **Adaptive process noise** - the prediction jitter grows when the cloud is
    degenerate (low Neff) or the terrain is uninformative, keeping the filter
    from collapsing prematurely.
  * **Mode awareness** - :meth:`modes` exposes the multi-hypothesis structure the
    coordinator uses to detect ambiguous terrain; :meth:`reinit_from` lets a
    confident sibling filter rescue an impoverished cloud.
"""

from __future__ import annotations

import numpy as np

from .. import estimation as est
from ..config import SimConfig
from ..terrain import Terrain

D = 6  # particle state dimension


class TerrainParticleFilter:
    def __init__(
        self,
        cfg: SimConfig,
        terrain: Terrain,
        pos0,
        vel0,
        rng: np.random.Generator | None = None,
    ):
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
        self._R = est.terrain_meas_var(cfg)
        self._q_scale = 1.0
        self._last_fix_pos: np.ndarray | None = None
        self._last_fix_t: float | None = None

    # ---- prediction (IMU driven) --------------------------------------- #
    def predict(self, accel_meas: np.ndarray, dt: float) -> None:
        cfg = self.cfg
        accel_meas = np.asarray(accel_meas, float)
        sigma_a = cfg.accel_noise / np.sqrt(dt) * np.sqrt(self._q_scale)
        a = accel_meas[None, :] - self.X[:, 4:6]
        a = a + self.rng.normal(0.0, sigma_a, (self.N, 2))
        self.X[:, 0:2] += self.X[:, 2:4] * dt + 0.5 * a * dt * dt
        self.X[:, 2:4] += a * dt
        self.X[:, 4:6] += self.rng.normal(
            0.0, cfg.accel_bias_rw * np.sqrt(dt), (self.N, 2)
        )

    # ---- measurement updates ------------------------------------------- #
    def _elev_var(self) -> np.ndarray:
        """Per-particle elevation-match variance (heteroscedastic, map-aware)."""
        cfg = self.cfg
        R = np.full(self.N, est.terrain_meas_var(cfg))
        if cfg.map_interp_frac > 0.0:
            h = cfg.terrain_res
            gx = (
                self.terrain.elevation(self.X[:, 0] + h, self.X[:, 1])
                - self.terrain.elevation(self.X[:, 0] - h, self.X[:, 1])
            ) / (2 * h)
            gy = (
                self.terrain.elevation(self.X[:, 0], self.X[:, 1] + h)
                - self.terrain.elevation(self.X[:, 0], self.X[:, 1] - h)
            ) / (2 * h)
            R = R + (cfg.map_interp_frac * h) ** 2 * (gx**2 + gy**2)
        return R

    def update_trn(self, ground_elev_meas: float) -> None:
        elev = self.terrain.elevation(self.X[:, 0], self.X[:, 1])
        innov = ground_elev_meas - elev
        R = self._elev_var()
        logw = np.log(self.w + 1e-300) - 0.5 * innov * innov / R
        self._set_weights(logw)
        self._adapt_process()
        self._maybe_resample()

    def _adapt_process(self) -> None:
        """Grow prediction jitter when the cloud is degenerate or terrain is
        uninformative; relax it back toward 1 otherwise."""
        cfg = self.cfg
        if not cfg.adapt_q:
            self._q_scale = 1.0
            return
        frac = self.neff() / self.N
        # low Neff (degenerate) -> inflate; healthy -> relax to 1
        neff_target = 1.0 + (cfg.adapt_q_max - 1.0) * float(
            np.clip((cfg.pf_neff_frac - frac) / max(cfg.pf_neff_frac, 1e-6), 0.0, 1.0)
        )
        if cfg.adapt_q_terrain:
            grad = self.terrain.gradient(self.pos[0], self.pos[1])
            info = float(grad @ grad)
            ref = cfg.adapt_q_terrain_ref**2
            terrain_target = 1.0 + (cfg.adapt_q_terrain_max - 1.0) / (
                1.0 + info / max(ref, 1e-9)
            )
        else:
            terrain_target = 1.0
        target = max(neff_target, terrain_target)
        self._q_scale += 0.3 * (target - self._q_scale)
        self._q_scale = float(
            np.clip(
                self._q_scale,
                cfg.adapt_q_min,
                cfg.adapt_q_max * cfg.adapt_q_terrain_max,
            )
        )

    def update_position(
        self, pos_fix: np.ndarray, cov: np.ndarray, t: float | None = None
    ) -> None:
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
            return  # reject outlier fix

        Rinv = np.linalg.inv(cov)
        d = self.X[:, 0:2] - pos_fix
        md = np.einsum("ni,ij,nj->n", d, Rinv, d)
        self._set_weights(np.log(self.w + 1e-300) - 0.5 * md)
        self._maybe_resample()

        w_eig, V = np.linalg.eigh(cov)
        fix_std = float(np.sqrt(max(w_eig.max(), 0.0)))
        m = int(self.cfg.pf_inject * self.N)
        if m > 0 and fix_std <= self.cfg.pf_inject_std_max:
            if (
                self._last_fix_pos is not None
                and t is not None
                and t > self._last_fix_t
            ):
                v_inj = (pos_fix - self._last_fix_pos) / (t - self._last_fix_t)
            else:
                v_inj = self.vel
            lo = (0.5 * self.cfg.tercom_search_step) ** 2
            hi = self.cfg.pf_inject_std_max**2
            cov_inj = V @ np.diag(np.clip(w_eig, lo, hi)) @ V.T
            L = np.linalg.cholesky(cov_inj + 1e-6 * np.eye(2))
            sel = np.argsort(self.w)[:m]  # replace weakest
            self.X[sel, 0:2] = pos_fix + self.rng.normal(0, 1, (m, 2)) @ L.T
            self.X[sel, 2:4] = v_inj + self.rng.normal(
                0, self.cfg.init_vel_std * 0.5, (m, 2)
            )
            self.w[sel] = 1.0 / self.N
            self.w /= self.w.sum()

        if t is not None:
            self._last_fix_pos = pos_fix.copy()
            self._last_fix_t = t

    def reinit_from(
        self,
        pos: np.ndarray,
        cov: np.ndarray,
        vel: np.ndarray | None = None,
        frac: float = 0.5,
    ) -> None:
        """Relocalise a fraction of the cloud around an external posterior.

        Used by the coordinator when a confident sibling filter (PMF/EKF) should
        rescue an impoverished or wrong-mode particle cloud. The weakest
        ``frac`` of particles are moved; weights are renormalised.
        """
        pos = np.asarray(pos, float)
        cov = np.asarray(cov, float)
        m = int(np.clip(frac, 0.0, 1.0) * self.N)
        if m <= 0:
            return
        w_eig, V = np.linalg.eigh(0.5 * (cov + cov.T))
        w_eig = np.clip(w_eig, (0.5 * self.cfg.terrain_res) ** 2, None)
        L = np.linalg.cholesky(V @ np.diag(w_eig) @ V.T + 1e-6 * np.eye(2))
        sel = np.argsort(self.w)[:m]
        self.X[sel, 0:2] = pos + self.rng.normal(0, 1, (m, 2)) @ L.T
        if vel is not None:
            self.X[sel, 2:4] = np.asarray(vel, float) + self.rng.normal(
                0, self.cfg.init_vel_std * 0.5, (m, 2)
            )
        self.w[sel] = 1.0 / self.N
        self.w /= self.w.sum()

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
        return float(1.0 / np.sum(self.w**2))

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

    # ---- mode / ambiguity awareness ------------------------------------ #
    def modes(self) -> list[tuple[np.ndarray, float]]:
        """Spatial modes of the weighted cloud (multi-hypothesis structure)."""
        return est.cluster_modes(self.X[:, 0:2], self.w, self.cfg.mode_cluster_radius)

    def n_modes(self) -> int:
        return est.mode_count(self.modes(), self.cfg.mode_mass_frac)

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
