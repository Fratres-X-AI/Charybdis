"""Allan-variance IMU characterization, grade presets, and SVP/tidal bias.

Provides IEEE-style Allan deviation analysis for simulated IMU data, named
grade presets (navigation / tactical / consumer), and an optional slow
sound-velocity-profile / tidal acceleration bias state in the sensor model.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

import numpy as np

from .config import SimConfig
from .terrain import Terrain
from .trajectory import generate_truth

IMUGradeName = Literal["navigation", "tactical", "consumer"]

IMU_GRADES: dict[str, dict[str, float]] = {
    "navigation": dict(accel_noise=0.015, accel_bias0=0.008, accel_bias_rw=0.0003,
                       gyro_noise=0.003, heading_bias0_deg=0.05),
    "tactical": dict(accel_noise=0.08, accel_bias0=0.05, accel_bias_rw=0.002,
                     gyro_noise=0.02, heading_bias0_deg=0.4),
    "consumer": dict(accel_noise=0.35, accel_bias0=0.15, accel_bias_rw=0.012,
                     gyro_noise=0.08, heading_bias0_deg=2.0),
}


def apply_imu_grade(cfg: SimConfig, grade: IMUGradeName = "tactical") -> SimConfig:
    """Return cfg with IMU noise parameters set from a named grade preset."""
    params = IMU_GRADES.get(grade, IMU_GRADES["tactical"])
    return replace(cfg, **params)


def allan_deviation(series: np.ndarray, dt: float,
                    max_tau_frac: float = 0.25) -> tuple[np.ndarray, np.ndarray]:
    """Compute overlapping Allan deviation sigma(tau) for a 1-D error sequence."""
    x = np.asarray(series, float).ravel()
    n = x.size
    if n < 8:
        return np.array([dt]), np.array([np.std(x) if n else 0.0])
    taus, sigmas = [], []
    m_max = max(2, int(n * max_tau_frac))
    m = 1
    while m < m_max:
        tau = m * dt
        k = n - 2 * m
        if k < 1:
            break
        theta = np.cumsum(x) * dt
        diff = theta[2 * m:2 * m + k] - 2 * theta[m:m + k] + theta[:k]
        sig = np.sqrt(0.5 / (k * tau * tau) * np.mean(diff * diff))
        taus.append(tau)
        sigmas.append(sig)
        m = m * 2 if m * 2 > m + 1 else m + 1
    return np.asarray(taus), np.asarray(sigmas)


@dataclass
class AllanResult:
    tau: np.ndarray
    sigma: np.ndarray
    white_noise: float
    bias_instability: float


def characterize_allan(series: np.ndarray, dt: float) -> AllanResult:
    """Allan deviation curve plus white-noise and bias-instability estimates."""
    tau, sigma = allan_deviation(series, dt)
    white = float(sigma[0]) if sigma.size else 0.0
    bias = float(np.min(sigma)) if sigma.size else 0.0
    return AllanResult(tau=tau, sigma=sigma, white_noise=white,
                       bias_instability=bias)


def simulate_accel_error(cfg: SimConfig, axis: int = 0) -> np.ndarray:
    """Simulate per-sample accelerometer error on one axis (for Allan analysis)."""
    from .imu import IMU
    terrain = Terrain.synthetic(cfg)
    truth = generate_truth(cfg, terrain)
    imu = IMU(cfg, terrain)
    err = np.empty(len(truth))
    for k in range(len(truth)):
        s = imu.sample(truth, k)
        err[k] = s.accel[axis] - truth.acc[k, axis]
    return err


def grade_allan_table(grades: tuple[str, ...] = ("navigation", "tactical", "consumer"),
                      duration: float = 120.0) -> dict[str, AllanResult]:
    """Allan metrics for each IMU grade preset."""
    out: dict[str, AllanResult] = {}
    for g in grades:
        cfg = apply_imu_grade(SimConfig(duration=duration, seed=11), g)
        err = simulate_accel_error(cfg)
        out[g] = characterize_allan(err, cfg.dt)
    return out
