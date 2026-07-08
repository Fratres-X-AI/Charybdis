"""Extended Kalman Filter for terrain-aided inertial navigation.

State:  x = [px, py, vx, vy, bax, bay]
  position / velocity in the local ENU nav frame plus accelerometer bias.

Prediction is driven by the measured specific force (IMU) as a control input.
Corrections come from two terrain sources:
  * TRN  - recursive single-point terrain-elevation match (Jacobian = DEM slope)
  * TERCOM - batch correlation position fix (direct position observation)
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .config import SimConfig
from .terrain import Terrain


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

        q_a = cfg.accel_noise ** 2
        q_b = cfg.accel_bias_rw ** 2
        Q = np.zeros((self.N, self.N))
        for i in range(2):
            Q[i, i] = q_a * dt ** 3 / 3.0
            Q[i, i + 2] = Q[i + 2, i] = q_a * dt ** 2 / 2.0
            Q[i + 2, i + 2] = q_a * dt
            Q[i + 4, i + 4] = q_b * dt
        self.P = F @ self.P @ F.T + Q

    # ---- terrain-referenced (single point) update ----------------------
    def update_trn(self, ground_elev_meas: float) -> UpdateInfo:
        px, py = self.x[0], self.x[1]
        h = float(self.terrain.elevation(px, py))
        grad = self.terrain.gradient(px, py)
        H = np.array([grad[0], grad[1], 0.0, 0.0, 0.0, 0.0])
        R = self.cfg.radar_noise ** 2 + self.cfg.baro_noise ** 2
        y = ground_elev_meas - h
        S = float(H @ self.P @ H.T + R)
        nis = y * y / S
        if nis > self.cfg.gate_chi2:       # scalar gate (generous)
            return UpdateInfo(False, y, nis)
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
    def pos_std(self) -> np.ndarray:
        return np.sqrt(np.diag(self.P)[0:2])
