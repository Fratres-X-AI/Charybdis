"""Small hybrid harbor-patrol simulation.

This is a deterministic software harness for the hybrid UUV foundation:
surface GPS, dive, submerged velocity/depth/bathymetry aiding, then resurface
and reacquire GPS. It is intentionally compact and sensor-abstract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np

from ..hybrid.fusion import HybridFusionConfig, HybridNavState, HybridSensorFusion
from ..hybrid.modes import NavMode
from ..hybrid.patrol import PatrolCommand, PatrolExecutor, PatrolRoute, Waypoint
from ..hybrid.sensors import (BathymetryMeasurement, DepthMeasurement, GpsMeasurement,
                              ImuMeasurement, SensorPacket, VelocityMeasurement)


@dataclass(frozen=True)
class HybridHarborConfig:
    dt: float = 1.0
    max_steps: int = 180
    seed: int = 11
    gps_noise_m: float = 1.5
    gps_vel_noise_mps: float = 0.08
    velocity_noise_mps: float = 0.05
    depth_noise_m: float = 0.15
    bathy_fix_noise_m: float = 3.0
    bathy_period_steps: int = 6
    accel_noise_mps2: float = 0.01
    depth_tau_s: float = 8.0
    route: PatrolRoute = field(default_factory=lambda: PatrolRoute((
        Waypoint([0.0, 0.0], mode=NavMode.SURFACE, depth_m=0.0, radius_m=3.0),
        Waypoint([35.0, 0.0], mode=NavMode.SURFACE, depth_m=0.0,
                 speed_mps=1.8, radius_m=4.0),
        Waypoint([55.0, 15.0], mode=NavMode.SUBMERGED, depth_m=8.0,
                 speed_mps=1.5, radius_m=9.0),
        Waypoint([55.0, 45.0], mode=NavMode.SUBMERGED, depth_m=8.0,
                 speed_mps=1.5, radius_m=9.0),
        Waypoint([20.0, 45.0], mode=NavMode.SUBMERGED, depth_m=8.0,
                 speed_mps=1.5, radius_m=9.0),
        Waypoint([0.0, 20.0], mode=NavMode.SURFACE, depth_m=0.0,
                 speed_mps=1.6, radius_m=8.0),
    )))


@dataclass(frozen=True)
class HybridHarborResult:
    truth_pos: np.ndarray
    est_pos: np.ndarray
    truth_depth: np.ndarray
    est_depth: np.ndarray
    modes: tuple[NavMode, ...]
    waypoint_index: np.ndarray
    pos_error: np.ndarray
    depth_error: np.ndarray
    route_complete: bool
    final_state: HybridNavState

    def summary(self) -> dict:
        return {
            "steps": int(self.pos_error.size),
            "route_complete": bool(self.route_complete),
            "final_error_m": float(self.pos_error[-1]),
            "mean_error_m": float(np.mean(self.pos_error)),
            "max_error_m": float(np.max(self.pos_error)),
            "final_depth_error_m": float(abs(self.depth_error[-1])),
            "used_surface": any(m == NavMode.SURFACE for m in self.modes),
            "used_submerged": any(m == NavMode.SUBMERGED for m in self.modes),
            "last_gps_t": self.final_state.last_gps_t,
            "last_bathy_t": self.final_state.last_bathy_t,
        }


def run_hybrid_harbor_simulation(
    cfg: HybridHarborConfig | None = None,
    fusion_cfg: HybridFusionConfig | None = None,
) -> HybridHarborResult:
    cfg = cfg or HybridHarborConfig()
    rng = np.random.default_rng(cfg.seed)
    patrol = PatrolExecutor(cfg.route, max_turn_rate_radps=np.deg2rad(120.0))
    fusion = HybridSensorFusion(
        pos0=cfg.route.waypoints[0].pos,
        vel0=np.zeros(2),
        depth0=cfg.route.waypoints[0].depth_m,
        cfg=fusion_cfg or HybridFusionConfig(
            init_pos_std=8.0,
            init_vel_std=0.4,
            depth_process_noise=0.8,
            depth_rate_noise=0.25,
        ),
    )

    truth_pos = cfg.route.waypoints[0].pos.astype(float).copy()
    truth_vel = np.zeros(2)
    truth_depth = float(cfg.route.waypoints[0].depth_m)
    last_vel = truth_vel.copy()

    truth_pos_hist, est_pos_hist = [], []
    truth_depth_hist, est_depth_hist = [], []
    modes, wp_idx = [], []

    state = fusion.state()
    route_complete = False
    for k in range(cfg.max_steps):
        cmd = patrol.update(state)
        truth_pos, truth_vel, truth_depth = _propagate_truth(
            truth_pos, truth_vel, truth_depth, cmd, cfg)
        accel = (truth_vel - last_vel) / cfg.dt
        last_vel = truth_vel.copy()

        packet = _make_packet(k, truth_pos, truth_vel, truth_depth, accel,
                              cmd, cfg, rng)
        state = fusion.step(packet)

        truth_pos_hist.append(truth_pos.copy())
        est_pos_hist.append(state.pos.copy())
        truth_depth_hist.append(truth_depth)
        est_depth_hist.append(state.depth_m)
        modes.append(state.mode)
        wp_idx.append(cmd.waypoint_index)
        route_complete = cmd.route_complete
        if route_complete:
            break

    truth_pos_arr = np.asarray(truth_pos_hist)
    est_pos_arr = np.asarray(est_pos_hist)
    truth_depth_arr = np.asarray(truth_depth_hist)
    est_depth_arr = np.asarray(est_depth_hist)
    return HybridHarborResult(
        truth_pos=truth_pos_arr,
        est_pos=est_pos_arr,
        truth_depth=truth_depth_arr,
        est_depth=est_depth_arr,
        modes=tuple(modes),
        waypoint_index=np.asarray(wp_idx, dtype=int),
        pos_error=np.linalg.norm(est_pos_arr - truth_pos_arr, axis=1),
        depth_error=est_depth_arr - truth_depth_arr,
        route_complete=route_complete,
        final_state=state,
    )


def _propagate_truth(pos: np.ndarray, vel: np.ndarray, depth: float,
                     cmd: PatrolCommand,
                     cfg: HybridHarborConfig) -> tuple[np.ndarray, np.ndarray, float]:
    dt = cfg.dt
    target_vel = np.asarray(cmd.desired_vel, dtype=float)
    vel = 0.65 * vel + 0.35 * target_vel
    pos = pos + vel * dt
    tau = max(cfg.depth_tau_s, dt)
    depth += (cmd.target_depth_m - depth) * min(dt / tau, 1.0)
    return pos, vel, float(depth)


def _make_packet(k: int, pos: np.ndarray, vel: np.ndarray, depth: float,
                 accel: np.ndarray, cmd: PatrolCommand,
                 cfg: HybridHarborConfig,
                 rng: np.random.Generator) -> SensorPacket:
    mode = cmd.target_mode
    gps = None
    if mode == NavMode.SURFACE:
        gps = GpsMeasurement(
            pos + rng.normal(0.0, cfg.gps_noise_m, size=2),
            vel + rng.normal(0.0, cfg.gps_vel_noise_mps, size=2),
            pos_cov=np.diag([cfg.gps_noise_m] * 2) ** 2,
            vel_cov=np.diag([cfg.gps_vel_noise_mps] * 2) ** 2,
        )

    velocity = None
    if mode == NavMode.SUBMERGED:
        velocity = VelocityMeasurement(
            vel + rng.normal(0.0, cfg.velocity_noise_mps, size=2),
            cov=np.diag([cfg.velocity_noise_mps] * 2) ** 2,
        )

    bathy = None
    if mode == NavMode.SUBMERGED and k % cfg.bathy_period_steps == 0:
        bathy = BathymetryMeasurement(
            pos_fix=pos + rng.normal(0.0, cfg.bathy_fix_noise_m, size=2),
            pos_cov=np.diag([cfg.bathy_fix_noise_m] * 2) ** 2,
        )

    return SensorPacket(
        imu=ImuMeasurement(
            accel + rng.normal(0.0, cfg.accel_noise_mps2, size=2),
            dt=cfg.dt,
        ),
        gps=gps,
        depth=DepthMeasurement(
            depth + rng.normal(0.0, cfg.depth_noise_m),
            var=cfg.depth_noise_m ** 2,
        ),
        velocity=velocity,
        bathymetry=bathy,
        mode_hint=mode,
    )
