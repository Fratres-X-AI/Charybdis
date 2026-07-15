"""Deterministic hybrid harbor simulation with terrain-profile aiding."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from ..hybrid.bathymetry import (
    BathymetryMap,
    BathymetryProfile,
    MatchStatus,
    TerrainMatcherConfig,
    TerrainProfileMatcher,
)
from ..hybrid.fusion import HybridFusionConfig, HybridNavState, HybridSensorFusion
from ..hybrid.modes import NavMode
from ..hybrid.navigator import HybridNavigator
from ..hybrid.patrol import PatrolCommand, PatrolExecutor, PatrolRoute, Waypoint
from ..hybrid.sensors import (
    DepthMeasurement,
    GpsMeasurement,
    ImuMeasurement,
    SensorPacket,
    VelocityMeasurement,
)

FloatArray = NDArray[np.float64]


def _default_route() -> PatrolRoute:
    return PatrolRoute(
        (
            Waypoint([0.0, 0.0], mode=NavMode.SURFACE, radius_m=3.0),
            Waypoint(
                [35.0, 0.0],
                mode=NavMode.SURFACE,
                speed_mps=1.8,
                radius_m=4.0,
            ),
            Waypoint(
                [55.0, 15.0],
                mode=NavMode.SUBMERGED,
                depth_m=8.0,
                speed_mps=1.5,
                radius_m=9.0,
            ),
            Waypoint(
                [55.0, 45.0],
                mode=NavMode.SUBMERGED,
                depth_m=8.0,
                speed_mps=1.5,
                radius_m=9.0,
            ),
            Waypoint(
                [20.0, 45.0],
                mode=NavMode.SUBMERGED,
                depth_m=8.0,
                speed_mps=1.5,
                radius_m=9.0,
            ),
            Waypoint(
                [0.0, 20.0],
                mode=NavMode.SURFACE,
                speed_mps=1.6,
                radius_m=8.0,
            ),
        )
    )


def _default_fusion_config() -> HybridFusionConfig:
    return HybridFusionConfig(
        init_pos_std=8.5,
        init_vel_std=0.4,
        depth_process_noise=0.8,
        depth_rate_noise=0.25,
    )


def _default_matcher_config() -> TerrainMatcherConfig:
    return TerrainMatcherConfig(
        search_radius_m=16.0,
        grid_step_m=2.0,
        prior_weight=0.2,
        min_profile_relief_m=0.5,
        min_cost_margin=0.2,
    )


@dataclass(frozen=True)
class HybridHarborConfig:
    """Serializable synthetic harbor scenario and sensor-fault settings."""

    name: str = "harbor_nominal"
    dt: float = 1.0
    max_steps: int = 240
    seed: int = 11
    gps_noise_m: float = 1.5
    gps_vel_noise_mps: float = 0.08
    velocity_noise_mps: float = 0.05
    depth_noise_m: float = 0.15
    bathy_profile_noise_m: float = 0.2
    bathy_period_steps: int = 6
    accel_noise_mps2: float = 0.01
    depth_tau_s: float = 8.0
    current_xy_mps: tuple[float, float] = (0.0, 0.0)
    initial_pos_error_xy_m: tuple[float, float] = (0.0, 0.0)
    gps_dropout_steps: tuple[int, int] | None = None
    velocity_dropout_steps: tuple[int, int] | None = None
    bathy_dropout_steps: tuple[int, int] | None = None
    bathy_outlier_steps: tuple[int, ...] = ()
    bathy_outlier_m: float = 8.0
    use_mode_hints: bool = False
    route: PatrolRoute = field(default_factory=_default_route)
    fusion: HybridFusionConfig = field(default_factory=_default_fusion_config)
    matcher: TerrainMatcherConfig = field(default_factory=_default_matcher_config)

    def __post_init__(self) -> None:
        positive = {
            "dt": self.dt,
            "gps_noise_m": self.gps_noise_m,
            "gps_vel_noise_mps": self.gps_vel_noise_mps,
            "velocity_noise_mps": self.velocity_noise_mps,
            "depth_noise_m": self.depth_noise_m,
            "bathy_profile_noise_m": self.bathy_profile_noise_m,
            "depth_tau_s": self.depth_tau_s,
        }
        non_negative = {
            "accel_noise_mps2": self.accel_noise_mps2,
            "bathy_outlier_m": self.bathy_outlier_m,
        }
        for name, value in positive.items():
            if not np.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        for name, value in non_negative.items():
            if not np.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.max_steps <= 0 or self.bathy_period_steps <= 0:
            raise ValueError("max_steps and bathy_period_steps must be positive")
        if not isinstance(self.seed, int):
            raise TypeError("seed must be int")
        if not isinstance(self.use_mode_hints, bool):
            raise TypeError("use_mode_hints must be bool")
        for name, vector in (
            ("current_xy_mps", self.current_xy_mps),
            ("initial_pos_error_xy_m", self.initial_pos_error_xy_m),
        ):
            if len(vector) != 2 or not np.all(np.isfinite(vector)):
                raise ValueError(f"{name} must contain two finite values")
        for name, window in (
            ("gps_dropout_steps", self.gps_dropout_steps),
            ("velocity_dropout_steps", self.velocity_dropout_steps),
            ("bathy_dropout_steps", self.bathy_dropout_steps),
        ):
            if window is not None and (
                len(window) != 2 or window[0] < 0 or window[1] <= window[0]
            ):
                raise ValueError(f"{name} must be a non-negative [start, stop) range")
        if any(step < 0 for step in self.bathy_outlier_steps):
            raise ValueError("bathy_outlier_steps must be non-negative")


@dataclass(frozen=True)
class HybridHarborResult:
    """Truth, estimates, consistency metrics, and matcher outcomes."""

    truth_pos: FloatArray
    est_pos: FloatArray
    truth_depth: FloatArray
    est_depth: FloatArray
    modes: tuple[NavMode, ...]
    waypoint_index: NDArray[np.int64]
    pos_error: FloatArray
    depth_error: FloatArray
    pos_nees: FloatArray
    depth_nees: FloatArray
    bathy_match_status: tuple[MatchStatus | None, ...]
    route_complete: bool
    final_state: HybridNavState
    bathymetry_map: BathymetryMap
    max_gps_reacquisition_jump_m: float = 0.0

    def summary(self) -> dict[str, int | float | bool | str | None]:
        """Return a JSON-compatible deterministic summary."""
        accepted_matches = sum(
            status == MatchStatus.ACCEPTED for status in self.bathy_match_status
        )
        attempted_matches = sum(
            status is not None for status in self.bathy_match_status
        )
        return {
            "scenario": "hybrid_harbor",
            "steps": int(self.pos_error.size),
            "route_complete": bool(self.route_complete),
            "final_error_m": float(self.pos_error[-1]),
            "mean_error_m": float(np.mean(self.pos_error)),
            "max_error_m": float(np.max(self.pos_error)),
            "final_depth_error_m": float(abs(self.depth_error[-1])),
            "position_anees": float(np.mean(self.pos_nees) / 2.0),
            "depth_anees": float(np.mean(self.depth_nees)),
            "bathy_matches_accepted": int(accepted_matches),
            "bathy_matches_attempted": int(attempted_matches),
            "fusion_rejections": self.final_state.diagnostics.total_rejections,
            "filter_healthy": self.final_state.filter_healthy,
            "used_surface": any(mode == NavMode.SURFACE for mode in self.modes),
            "used_submerged": any(mode == NavMode.SUBMERGED for mode in self.modes),
            "last_gps_t": self.final_state.last_gps_t,
            "last_bathy_t": self.final_state.last_bathy_t,
            "max_gps_reacquisition_jump_m": float(self.max_gps_reacquisition_jump_m),
        }


def build_synthetic_harbor_map(seed: int = 101) -> BathymetryMap:
    """Build a deterministic, distinctive positive-down harbor floor."""
    rng = np.random.default_rng(seed)
    resolution = 1.0
    origin = (-40.0, -40.0)
    coordinates = np.arange(0.0, 161.0, resolution)
    x_grid, y_grid = np.meshgrid(coordinates, coordinates)
    depth = (
        28.0
        + 3.0 * np.sin(x_grid / 8.0)
        + 2.5 * np.cos(y_grid / 11.0)
        + 1.8 * np.sin((x_grid + y_grid) / 6.0)
    )
    for _ in range(8):
        center = rng.uniform(20.0, 140.0, size=2)
        width = rng.uniform(5.0, 14.0)
        amplitude = rng.uniform(-3.0, 3.0)
        depth += amplitude * np.exp(
            -((x_grid - center[0]) ** 2 + (y_grid - center[1]) ** 2) / (2.0 * width**2)
        )
    return BathymetryMap(depth, resolution, origin_xy_m=origin)


def run_hybrid_harbor_simulation(
    cfg: HybridHarborConfig | None = None,
    fusion_cfg: HybridFusionConfig | None = None,
) -> HybridHarborResult:
    """Run one deterministic harbor scenario without parallel workers."""
    cfg = cfg or HybridHarborConfig()
    rng = np.random.default_rng(cfg.seed)
    bathymetry_map = build_synthetic_harbor_map()
    matcher = TerrainProfileMatcher(bathymetry_map, cfg.matcher)
    patrol = PatrolExecutor(cfg.route, max_turn_rate_radps=np.deg2rad(120.0))

    truth_pos = np.asarray(cfg.route.waypoints[0].pos, dtype=float).copy()
    initial_error = np.asarray(cfg.initial_pos_error_xy_m, dtype=float)
    fusion = HybridSensorFusion(
        pos0=truth_pos + initial_error,
        vel0=np.zeros(2),
        depth0=cfg.route.waypoints[0].depth_m,
        cfg=fusion_cfg or cfg.fusion,
    )
    navigator = HybridNavigator(fusion, patrol)
    state = fusion.state()
    command = patrol.update(state)

    truth_vel = np.zeros(2)
    truth_depth = float(cfg.route.waypoints[0].depth_m)
    last_vel = truth_vel.copy()
    truth_pos_history: list[FloatArray] = []
    est_pos_history: list[FloatArray] = []
    truth_depth_history: list[float] = []
    est_depth_history: list[float] = []
    modes: list[NavMode] = []
    waypoint_indices: list[int] = []
    position_nees: list[float] = []
    depth_nees: list[float] = []
    match_statuses: list[MatchStatus | None] = []
    gps_reacquisition_jumps: list[float] = []
    had_gps_prev = False
    had_gps_ever = False

    for step in range(cfg.max_steps):
        truth_pos, truth_vel, truth_depth = _propagate_truth(
            truth_pos,
            truth_vel,
            truth_depth,
            command,
            cfg,
        )
        acceleration = (truth_vel - last_vel) / cfg.dt
        last_vel = truth_vel.copy()
        packet, match_status = _make_packet(
            step,
            truth_pos,
            truth_vel,
            truth_depth,
            acceleration,
            state,
            command,
            bathymetry_map,
            matcher,
            cfg,
            rng,
        )
        pos_before = state.pos.copy()
        gps_now = packet.gps is not None
        cycle = navigator.step(packet)
        state = cycle.state
        command = cycle.command
        if gps_now and not had_gps_prev and had_gps_ever:
            gps_reacquisition_jumps.append(
                float(np.linalg.norm(state.pos - pos_before))
            )
        if gps_now:
            had_gps_ever = True
        had_gps_prev = gps_now

        error = state.pos - truth_pos
        truth_pos_history.append(truth_pos.copy())
        est_pos_history.append(state.pos.copy())
        truth_depth_history.append(truth_depth)
        est_depth_history.append(state.depth_m)
        modes.append(state.mode)
        waypoint_indices.append(command.waypoint_index)
        position_nees.append(float(error @ np.linalg.pinv(state.pos_cov) @ error))
        depth_error = state.depth_m - truth_depth
        depth_nees.append(float(depth_error**2 / max(state.cov[2, 2], 1e-12)))
        match_statuses.append(match_status)
        if command.route_complete:
            break

    truth_pos_array = np.asarray(truth_pos_history)
    est_pos_array = np.asarray(est_pos_history)
    truth_depth_array = np.asarray(truth_depth_history)
    est_depth_array = np.asarray(est_depth_history)
    max_gps_jump = float(
        max(gps_reacquisition_jumps) if gps_reacquisition_jumps else 0.0
    )
    return HybridHarborResult(
        truth_pos=truth_pos_array,
        est_pos=est_pos_array,
        truth_depth=truth_depth_array,
        est_depth=est_depth_array,
        modes=tuple(modes),
        waypoint_index=np.asarray(waypoint_indices, dtype=np.int64),
        pos_error=np.linalg.norm(est_pos_array - truth_pos_array, axis=1),
        depth_error=est_depth_array - truth_depth_array,
        pos_nees=np.asarray(position_nees),
        depth_nees=np.asarray(depth_nees),
        bathy_match_status=tuple(match_statuses),
        route_complete=command.route_complete,
        final_state=state,
        bathymetry_map=bathymetry_map,
        max_gps_reacquisition_jump_m=max_gps_jump,
    )


def _propagate_truth(
    pos: FloatArray,
    vel: FloatArray,
    depth: float,
    command: PatrolCommand,
    cfg: HybridHarborConfig,
) -> tuple[FloatArray, FloatArray, float]:
    target_velocity = np.asarray(command.desired_vel, dtype=float)
    current = np.asarray(cfg.current_xy_mps, dtype=float)
    velocity = 0.65 * vel + 0.35 * target_velocity + current
    position = pos + velocity * cfg.dt
    tau = max(cfg.depth_tau_s, cfg.dt)
    next_depth = depth + ((command.target_depth_m - depth) * min(cfg.dt / tau, 1.0))
    return position, velocity, max(float(next_depth), 0.0)


def _make_packet(
    step: int,
    pos: FloatArray,
    vel: FloatArray,
    depth: float,
    accel: FloatArray,
    prior_state: HybridNavState,
    command: PatrolCommand,
    bathymetry_map: BathymetryMap,
    matcher: TerrainProfileMatcher,
    cfg: HybridHarborConfig,
    rng: np.random.Generator,
) -> tuple[SensorPacket, MatchStatus | None]:
    timestamp = (step + 1) * cfg.dt
    surface = depth <= cfg.fusion.mode.surface_depth_m
    submerged = depth >= cfg.fusion.mode.submerged_depth_m

    gps = None
    if surface and not _in_window(step, cfg.gps_dropout_steps):
        gps = GpsMeasurement(
            pos + rng.normal(0.0, cfg.gps_noise_m, size=2),
            vel + rng.normal(0.0, cfg.gps_vel_noise_mps, size=2),
            pos_cov=np.diag([cfg.gps_noise_m] * 2) ** 2,
            vel_cov=np.diag([cfg.gps_vel_noise_mps] * 2) ** 2,
            timestamp_s=timestamp,
        )

    velocity = None
    if submerged and not _in_window(step, cfg.velocity_dropout_steps):
        velocity = VelocityMeasurement(
            vel + rng.normal(0.0, cfg.velocity_noise_mps, size=2),
            cov=np.diag([cfg.velocity_noise_mps] * 2) ** 2,
            timestamp_s=timestamp,
        )

    bathymetry = None
    match_status = None
    bathy_due = submerged and step % cfg.bathy_period_steps == 0
    if bathy_due and not _in_window(step, cfg.bathy_dropout_steps):
        profile_offsets = _profile_offsets()
        profile_depths = bathymetry_map.sample(pos + profile_offsets)
        profile_depths = profile_depths + rng.normal(
            0.0,
            cfg.bathy_profile_noise_m,
            size=profile_depths.shape,
        )
        if step in cfg.bathy_outlier_steps:
            distortion = np.linspace(
                -cfg.bathy_outlier_m,
                cfg.bathy_outlier_m,
                profile_depths.size,
            )
            profile_depths = profile_depths + distortion
        profile = BathymetryProfile(
            offsets_xy_m=profile_offsets,
            bottom_depth_m=profile_depths,
            variance_m2=cfg.bathy_profile_noise_m**2,
            timestamp_s=timestamp,
        )
        match = matcher.match(
            profile,
            prior_pos=prior_state.pos,
            prior_cov=prior_state.pos_cov,
        )
        match_status = match.status
        bathymetry = match.measurement

    measured_depth = max(
        depth + float(rng.normal(0.0, cfg.depth_noise_m)),
        0.0,
    )
    return (
        SensorPacket(
            imu=ImuMeasurement(
                accel + rng.normal(0.0, cfg.accel_noise_mps2, size=2),
                dt=cfg.dt,
                timestamp_s=timestamp,
            ),
            gps=gps,
            depth=DepthMeasurement(
                measured_depth,
                var=cfg.depth_noise_m**2,
                timestamp_s=timestamp,
            ),
            velocity=velocity,
            bathymetry=bathymetry,
            mode_hint=command.target_mode if cfg.use_mode_hints else None,
            timestamp_s=timestamp,
        ),
        match_status,
    )


def _profile_offsets() -> FloatArray:
    axis = np.array([-8.0, 0.0, 8.0])
    x_grid, y_grid = np.meshgrid(axis, axis)
    return np.column_stack((x_grid.ravel(), y_grid.ravel()))


def _in_window(step: int, window: tuple[int, int] | None) -> bool:
    return window is not None and window[0] <= step < window[1]


__all__ = [
    "HybridHarborConfig",
    "HybridHarborResult",
    "build_synthetic_harbor_map",
    "run_hybrid_harbor_simulation",
]
