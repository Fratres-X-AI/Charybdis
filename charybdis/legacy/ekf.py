"""Extended Kalman Filter for terrain-aided inertial navigation.

State:  x = [px, py, vx, vy, bax, bay]
  position / velocity in the local ENU nav frame plus accelerometer bias.

Prediction is driven by the measured specific force (IMU) as a control input.
Corrections come from two terrain sources:
  * TRN  - recursive single-point terrain-elevation match (Jacobian = DEM slope)
  * TERCOM - batch correlation position fix (direct position observation)

Prime-level robustness features (all optional, see :class:`SimConfig`):
  * **Stochastic linearisation** of the DEM (:func:`estimation.stochastic_linearize`)
    - the slope Jacobian is averaged over the position prior and the plane's
    residual variance is added to the measurement noise, so the filter stays
    consistent when the position error is large (the classic EKF-TRN failure).
  * **Map-uncertainty budget** - the stored bathymetry is treated as noisy, not
    ground truth (``cfg.map_sigma`` + slope-projected interpolation error).
  * **Adaptive process noise** - Q is scaled up from the recent innovation
    statistics (covariance matching) and inflated further in low-information
    terrain, guarding against covariance collapse / overconfidence.
  * **PF-driven recovery** - :meth:`reset_from` lets the coordinator rescue a
    diverged EKF from the particle-filter posterior.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from ..config import SimConfig
from ..terrain import Terrain
from .. import estimation as est


@dataclass
class UpdateInfo:
    accepted: bool
    innovation: float
    nis: float               # normalised innovation squared


class NavEKF:
    N = 6

    def __init__(self, cfg: SimConfig, terrain: Terrain, pos0, vel0):
        self.cfg = cfg
        self.terrain = terrain
        self.x = np.zeros(self.N)
        self.x[0:2] = pos0
        self.x[2:4] = vel0
        p = np.zeros(self.N)
        p[0:2] = cfg.init_pos_std ** 2
        p[2:4] = cfg.init_vel_std ** 2
        p[4:6] = cfg.accel_bias0 ** 2
        self.P = np.diag(p)
        self.monitor = est.InnovationMonitor(cfg.adapt_q_window, dof=1)
        self.n_resets = 0
        self.last_q_scale = 1.0

    # ---- prediction ----------------------------------------------------
    def predict(self, accel_meas: np.ndarray, dt: float) -> None:
        cfg = self.cfg
        b = self.x[4:6]
        a = np.asarray(accel_meas, float) - b
        self.x[0:2] += self.x[2:4] * dt + 0.5 * a * dt * dt
        self.x[2:4] += a * dt
        # bias constant in mean

        F = np.eye(self.N)
        F[0:2, 2:4] = np.eye(2) * dt
        F[0:2, 4:6] = -0.5 * dt * dt * np.eye(2)
        F[2:4, 4:6] = -dt * np.eye(2)

        q_scale = self._q_scale()
        self.last_q_scale = q_scale
        q_a = cfg.accel_noise ** 2 * q_scale
        q_b = cfg.accel_bias_rw ** 2
        Q = np.zeros((self.N, self.N))
        for i in range(2):
            Q[i, i] = q_a * dt ** 3 / 3.0
            Q[i, i + 2] = Q[i + 2, i] = q_a * dt ** 2 / 2.0
            Q[i + 2, i + 2] = q_a * dt
            Q[i + 4, i + 4] = q_b * dt
        self.P = F @ self.P @ F.T + Q

    def _q_scale(self) -> float:
        """Adaptive process-noise multiplier (innovation + terrain driven)."""
        cfg = self.cfg
        scale = 1.0
        if cfg.adapt_q:
            scale *= self.monitor.q_scale(
                cfg.adapt_q_min, cfg.adapt_q_max, cfg.adapt_q_min_count)
        if cfg.adapt_q_terrain:
            grad = self.terrain.gradient(self.x[0], self.x[1])
            info = float(grad @ grad)                 # slope Fisher proxy
            ref = cfg.adapt_q_terrain_ref ** 2
            factor = 1.0 + (cfg.adapt_q_terrain_max - 1.0) / (1.0 + info / max(ref, 1e-9))
            scale *= float(np.clip(factor, 1.0, cfg.adapt_q_terrain_max))
        return float(np.clip(scale, cfg.adapt_q_min,
                             cfg.adapt_q_max * cfg.adapt_q_terrain_max))

    # ---- terrain-referenced (single point) update ----------------------
    def update_trn(self, ground_elev_meas: float) -> UpdateInfo:
        cfg = self.cfg
        px, py = self.x[0], self.x[1]
        R_base = est.terrain_meas_var(cfg)
        if cfg.ekf_stochastic_lin:
            h, grad, R_lin = est.stochastic_linearize(
                self.terrain, self.x[0:2], self.P[0:2, 0:2], cfg)
            R = R_base + R_lin
        else:
            h = float(self.terrain.elevation(px, py))
            grad = self.terrain.gradient(px, py)
            R = est.terrain_meas_var(cfg, slope=float(np.hypot(*grad)))
        H = np.array([grad[0], grad[1], 0.0, 0.0, 0.0, 0.0])
        y = ground_elev_meas - h
        S = float(H @ self.P @ H.T + R)
        nis = y * y / S
        if nis > cfg.gate_chi2:            # scalar gate (generous)
            # Repeated rejects are a real health signal. Cap the value so one
            # gross altimeter spike cannot dominate the adaptive-Q history.
            self.monitor.push(min(nis, 2.0 * cfg.gate_chi2))
            return UpdateInfo(False, y, nis)
        self.monitor.push(nis)
        K = (self.P @ H) / S
        self.x = self.x + K * y
        self._joseph(H.reshape(1, -1), np.array([[R]]), K.reshape(-1, 1))
        return UpdateInfo(True, y, nis)

    # ---- TERCOM position fix update ------------------------------------
    def update_position(self, pos_fix: np.ndarray, cov: np.ndarray) -> UpdateInfo:
        H = np.zeros((2, self.N))
        H[0, 0] = H[1, 1] = 1.0
        R = np.asarray(cov, float)
        y = np.asarray(pos_fix, float) - self.x[0:2]
        S = H @ self.P @ H.T + R
        Si = np.linalg.inv(S)
        nis = float(y @ Si @ y)
        if nis > self.cfg.gate_chi2:
            return UpdateInfo(False, float(np.linalg.norm(y)), nis)
        K = self.P @ H.T @ Si
        self.x = self.x + K @ y
        self._joseph(H, R, K)
        return UpdateInfo(True, float(np.linalg.norm(y)), nis)

    # ---- PF-driven recovery -------------------------------------------
    def reset_from(self, pos: np.ndarray, cov: np.ndarray,
                   vel: np.ndarray | None = None,
                   vel_cov: np.ndarray | None = None,
                   infl: float = 1.0) -> None:
        """Re-seed the position marginal (and optionally velocity) from an
        external, more-trustworthy posterior - the recovery hook the coordinator
        uses when the robust filters flag the EKF as diverged. Cross-covariances
        to the injected states are cleared and the biases are kept but their
        uncertainty is inflated, so the re-seeded filter is not over-confident.
        """
        pos = np.asarray(pos, float)
        self.x[0:2] = pos
        self.P[0:2, :] = 0.0
        self.P[:, 0:2] = 0.0
        self.P[0:2, 0:2] = infl * np.asarray(cov, float)
        if vel is not None:
            self.x[2:4] = np.asarray(vel, float)
            self.P[2:4, :] = 0.0
            self.P[:, 2:4] = 0.0
            vc = np.asarray(vel_cov, float) if vel_cov is not None \
                else np.diag([self.cfg.init_vel_std ** 2] * 2)
            self.P[2:4, 2:4] = infl * vc
        # keep bias mean, but re-open its uncertainty
        self.P[4:6, 4:6] = np.maximum(self.P[4:6, 4:6],
                                      np.diag([self.cfg.accel_bias0 ** 2] * 2))
        self.P = 0.5 * (self.P + self.P.T)
        self.monitor.buf.clear()
        self.n_resets += 1

    def _joseph(self, H: np.ndarray, R: np.ndarray, K: np.ndarray) -> None:
        I = np.eye(self.N)
        A = I - K @ H
        self.P = A @ self.P @ A.T + K @ R @ K.T
        self.P = 0.5 * (self.P + self.P.T)

    # ---- accessors -----------------------------------------------------
    @property
    def pos(self) -> np.ndarray:
        return self.x[0:2].copy()

    @property
    def vel(self) -> np.ndarray:
        return self.x[2:4].copy()

    @property
    def pos_cov(self) -> np.ndarray:
        return self.P[0:2, 0:2].copy()

    @property
    def pos_std(self) -> np.ndarray:
        return np.sqrt(np.diag(self.P)[0:2])
