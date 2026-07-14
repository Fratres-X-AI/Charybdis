"""Deterministic sensor-packet log replay for hybrid integration testing."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np

from ..hybrid.fusion import HybridFusionConfig, HybridSensorFusion
from ..hybrid.modes import ModeManagerConfig, NavMode
from ..hybrid.navigator import HybridNavigator, HybridStepResult
from ..hybrid.patrol import PatrolExecutor, PatrolRoute, Waypoint
from ..hybrid.sensors import (
    BathymetryMeasurement,
    DepthMeasurement,
    GpsMeasurement,
    ImuMeasurement,
    SensorPacket,
    SensorQuality,
    VelocityMeasurement,
)
from ..simulation.hybrid import (
    HybridHarborConfig,
    _make_packet,
    _propagate_truth,
    build_synthetic_harbor_map,
)

_MEASUREMENT_TYPES: dict[str, type[Any]] = {
    "ImuMeasurement": ImuMeasurement,
    "GpsMeasurement": GpsMeasurement,
    "DepthMeasurement": DepthMeasurement,
    "VelocityMeasurement": VelocityMeasurement,
    "BathymetryMeasurement": BathymetryMeasurement,
    "SensorQuality": SensorQuality,
}


def _jsonify(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, np.ndarray):
        return value.tolist()
    if is_dataclass(value):
        return {
            field.name: _jsonify(getattr(value, field.name)) for field in fields(value)
        }
    if isinstance(value, dict):
        return {key: _jsonify(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonify(item) for item in value]
    return value


def _build_measurement(cls: type[Any], data: dict[str, Any]) -> Any:
    kwargs: dict[str, Any] = {}
    for field in fields(cls):
        raw = data[field.name]
        if field.name == "quality":
            kwargs[field.name] = SensorQuality(**raw)
        elif isinstance(raw, list) and field.name in {
            "pos",
            "vel",
            "accel",
            "pos_fix",
            "offsets_xy_m",
        }:
            kwargs[field.name] = raw
        elif isinstance(raw, list) and field.name in {"pos_cov", "vel_cov", "cov"}:
            kwargs[field.name] = np.asarray(raw, dtype=float)
        else:
            kwargs[field.name] = raw
    return cls(**kwargs)


_PACKET_FIELD_TYPES: dict[str, type[Any]] = {
    "imu": ImuMeasurement,
    "gps": GpsMeasurement,
    "depth": DepthMeasurement,
    "velocity": VelocityMeasurement,
    "bathymetry": BathymetryMeasurement,
}


def packet_to_dict(packet: SensorPacket) -> dict[str, Any]:
    """Return a JSON-compatible packet representation."""
    return _jsonify(packet)


def packet_from_dict(data: dict[str, Any]) -> SensorPacket:
    """Rebuild a packet from :func:`packet_to_dict` output."""
    kwargs: dict[str, Any] = {}
    for key, raw in data.items():
        if raw is None:
            kwargs[key] = None
        elif key == "mode_hint":
            kwargs[key] = NavMode(raw)
        elif key in _PACKET_FIELD_TYPES:
            kwargs[key] = _build_measurement(_PACKET_FIELD_TYPES[key], raw)
        else:
            kwargs[key] = raw
    return SensorPacket(**kwargs)


def _waypoint_from_dict(data: dict[str, Any]) -> Waypoint:
    return Waypoint(
        data["pos"],
        mode=NavMode(data["mode"]),
        depth_m=float(data["depth_m"]),
        speed_mps=float(data["speed_mps"]),
        radius_m=float(data["radius_m"]),
        heading_rad=data.get("heading_rad"),
        heading_tolerance_rad=float(data["heading_tolerance_rad"]),
        lookahead_m=float(data["lookahead_m"]),
        depth_tolerance_m=float(data["depth_tolerance_m"]),
    )


def _harbor_config_from_dict(data: dict[str, Any]) -> HybridHarborConfig:
    route = PatrolRoute(
        tuple(_waypoint_from_dict(item) for item in data["route"]["waypoints"]),
        loop=bool(data["route"].get("loop", False)),
    )
    fusion_data = data["fusion"]
    fusion = HybridFusionConfig(
        init_pos_std=float(fusion_data["init_pos_std"]),
        init_depth_std=float(fusion_data["init_depth_std"]),
        init_vel_std=float(fusion_data["init_vel_std"]),
        init_depth_rate_std=float(fusion_data["init_depth_rate_std"]),
        init_bias_std=float(fusion_data["init_bias_std"]),
        accel_noise=float(fusion_data["accel_noise"]),
        depth_process_noise=float(fusion_data["depth_process_noise"]),
        depth_rate_noise=float(fusion_data["depth_rate_noise"]),
        depth_rate_tau_s=float(fusion_data["depth_rate_tau_s"]),
        accel_bias_rw=float(fusion_data["accel_bias_rw"]),
        gps_gate_chi2=float(fusion_data["gps_gate_chi2"]),
        depth_gate_chi2=float(fusion_data["depth_gate_chi2"]),
        velocity_gate_chi2=float(fusion_data["velocity_gate_chi2"]),
        bathy_gate_chi2=float(fusion_data["bathy_gate_chi2"]),
        min_cov=float(fusion_data["min_cov"]),
        rejection_history_size=int(fusion_data["rejection_history_size"]),
        health_window_s=float(fusion_data["health_window_s"]),
        max_recent_rejections=int(fusion_data["max_recent_rejections"]),
        max_position_std_m=float(fusion_data["max_position_std_m"]),
        aiding_timeout_s=float(fusion_data["aiding_timeout_s"]),
        mode=ModeManagerConfig(**fusion_data["mode"]),
    )
    matcher_data = data["matcher"]
    from ..hybrid.bathymetry import TerrainMatcherConfig

    matcher = TerrainMatcherConfig(
        search_radius_m=float(matcher_data["search_radius_m"]),
        grid_step_m=float(matcher_data["grid_step_m"]),
        prior_weight=float(matcher_data["prior_weight"]),
        min_profile_relief_m=float(matcher_data["min_profile_relief_m"]),
        min_cost_margin=float(matcher_data["min_cost_margin"]),
    )
    return HybridHarborConfig(
        name=str(data["name"]),
        dt=float(data["dt"]),
        max_steps=int(data["max_steps"]),
        seed=int(data["seed"]),
        gps_noise_m=float(data["gps_noise_m"]),
        gps_vel_noise_mps=float(data["gps_vel_noise_mps"]),
        velocity_noise_mps=float(data["velocity_noise_mps"]),
        depth_noise_m=float(data["depth_noise_m"]),
        bathy_profile_noise_m=float(data["bathy_profile_noise_m"]),
        bathy_period_steps=int(data["bathy_period_steps"]),
        accel_noise_mps2=float(data["accel_noise_mps2"]),
        depth_tau_s=float(data["depth_tau_s"]),
        current_xy_mps=tuple(data["current_xy_mps"]),
        initial_pos_error_xy_m=tuple(data["initial_pos_error_xy_m"]),
        gps_dropout_steps=(
            tuple(data["gps_dropout_steps"]) if data.get("gps_dropout_steps") else None
        ),
        velocity_dropout_steps=(
            tuple(data["velocity_dropout_steps"])
            if data.get("velocity_dropout_steps")
            else None
        ),
        bathy_dropout_steps=(
            tuple(data["bathy_dropout_steps"])
            if data.get("bathy_dropout_steps")
            else None
        ),
        bathy_outlier_steps=tuple(data.get("bathy_outlier_steps", ())),
        bathy_outlier_m=float(data["bathy_outlier_m"]),
        use_mode_hints=bool(data["use_mode_hints"]),
        route=route,
        fusion=fusion,
        matcher=matcher,
    )


class ReplayManifest:
    """Everything required to reconstruct a navigator for packet replay."""

    __slots__ = (
        "schema_version",
        "charybdis_version",
        "harbor_config",
        "pos0",
        "vel0",
        "depth0",
        "patrol_max_turn_rate_radps",
        "max_steps",
    )

    def __init__(
        self,
        *,
        schema_version: str,
        charybdis_version: str,
        harbor_config: dict[str, Any],
        pos0: tuple[float, float],
        vel0: tuple[float, float],
        depth0: float,
        patrol_max_turn_rate_radps: float,
        max_steps: int,
    ) -> None:
        self.schema_version = schema_version
        self.charybdis_version = charybdis_version
        self.harbor_config = harbor_config
        self.pos0 = pos0
        self.vel0 = vel0
        self.depth0 = depth0
        self.patrol_max_turn_rate_radps = patrol_max_turn_rate_radps
        self.max_steps = max_steps

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "charybdis_version": self.charybdis_version,
            "harbor_config": self.harbor_config,
            "pos0": list(self.pos0),
            "vel0": list(self.vel0),
            "depth0": self.depth0,
            "patrol_max_turn_rate_radps": self.patrol_max_turn_rate_radps,
            "max_steps": self.max_steps,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReplayManifest:
        return cls(
            schema_version=str(data["schema_version"]),
            charybdis_version=str(data["charybdis_version"]),
            harbor_config=dict(data["harbor_config"]),
            pos0=tuple(data["pos0"]),
            vel0=tuple(data["vel0"]),
            depth0=float(data["depth0"]),
            patrol_max_turn_rate_radps=float(data["patrol_max_turn_rate_radps"]),
            max_steps=int(data["max_steps"]),
        )


class ReplayLog:
    """Serialized packet stream plus navigator reconstruction metadata."""

    __slots__ = ("manifest", "packets")

    def __init__(
        self,
        *,
        manifest: ReplayManifest,
        packets: tuple[dict[str, Any], ...],
    ) -> None:
        self.manifest = manifest
        self.packets = packets

    def to_dict(self) -> dict[str, Any]:
        return {"manifest": self.manifest.to_dict(), "packets": list(self.packets)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReplayLog:
        return cls(
            manifest=ReplayManifest.from_dict(data["manifest"]),
            packets=tuple(data["packets"]),
        )


def step_snapshot(result: HybridStepResult) -> dict[str, Any]:
    """Capture replay-comparable state/command fields for one cycle."""
    state = result.state
    command = result.command
    return {
        "pos": state.pos.tolist(),
        "vel": state.vel.tolist(),
        "depth_m": float(state.depth_m),
        "mode": state.mode.value,
        "filter_healthy": bool(state.filter_healthy),
        "waypoint_index": int(command.waypoint_index),
        "route_complete": bool(command.route_complete),
    }


def record_harbor_packets(
    cfg: HybridHarborConfig | None = None,
    *,
    max_steps: int | None = None,
) -> ReplayLog:
    """Record deterministic harbor packets from the synthetic simulator."""
    import charybdis

    from ..hybrid.bathymetry import TerrainProfileMatcher

    cfg = cfg or HybridHarborConfig()
    steps = min(max_steps or cfg.max_steps, cfg.max_steps)
    rng = np.random.default_rng(cfg.seed)
    bathymetry_map = build_synthetic_harbor_map()
    matcher = TerrainProfileMatcher(bathymetry_map, cfg.matcher)

    truth_pos = np.asarray(cfg.route.waypoints[0].pos, dtype=float).copy()
    initial_error = np.asarray(cfg.initial_pos_error_xy_m, dtype=float)
    pos0 = truth_pos + initial_error
    fusion = HybridSensorFusion(
        pos0=pos0,
        vel0=np.zeros(2),
        depth0=cfg.route.waypoints[0].depth_m,
        cfg=cfg.fusion,
    )
    patrol = PatrolExecutor(cfg.route, max_turn_rate_radps=np.deg2rad(120.0))
    navigator = HybridNavigator(fusion, patrol)
    state = fusion.state()
    command = patrol.update(state)

    truth_vel = np.zeros(2)
    truth_depth = float(cfg.route.waypoints[0].depth_m)
    last_vel = truth_vel.copy()
    packets: list[dict[str, Any]] = []

    for step in range(steps):
        truth_pos, truth_vel, truth_depth = _propagate_truth(
            truth_pos,
            truth_vel,
            truth_depth,
            command,
            cfg,
        )
        acceleration = (truth_vel - last_vel) / cfg.dt
        last_vel = truth_vel.copy()
        packet, _ = _make_packet(
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
        packets.append(packet_to_dict(packet))
        cycle = navigator.step(packet)
        state = cycle.state
        command = cycle.command

    manifest = ReplayManifest(
        schema_version="1",
        charybdis_version=getattr(charybdis, "__version__", "unknown"),
        harbor_config=_jsonify(cfg),
        pos0=tuple(pos0.tolist()),
        vel0=(0.0, 0.0),
        depth0=float(cfg.route.waypoints[0].depth_m),
        patrol_max_turn_rate_radps=float(np.deg2rad(120.0)),
        max_steps=steps,
    )
    return ReplayLog(manifest=manifest, packets=tuple(packets))


def build_navigator_from_manifest(manifest: ReplayManifest) -> HybridNavigator:
    """Reconstruct a navigator from replay metadata."""
    cfg = _harbor_config_from_dict(manifest.harbor_config)
    patrol = PatrolExecutor(
        cfg.route,
        max_turn_rate_radps=manifest.patrol_max_turn_rate_radps,
    )
    fusion = HybridSensorFusion(
        pos0=np.asarray(manifest.pos0, dtype=float),
        vel0=np.asarray(manifest.vel0, dtype=float),
        depth0=manifest.depth0,
        cfg=cfg.fusion,
    )
    return HybridNavigator(fusion, patrol)


def replay_packets(
    log: ReplayLog,
    *,
    navigator: HybridNavigator | None = None,
) -> list[HybridStepResult]:
    """Feed recorded packets through a fresh navigator."""
    nav = navigator or build_navigator_from_manifest(log.manifest)
    return [nav.step(packet_from_dict(packet_dict)) for packet_dict in log.packets]


def assert_replay_matches(
    reference: Sequence[HybridStepResult],
    replayed: Sequence[HybridStepResult],
    *,
    pos_tol_m: float = 1e-9,
    vel_tol_mps: float = 1e-9,
) -> None:
    """Raise AssertionError when replay diverges from the reference cycle."""
    if len(reference) != len(replayed):
        raise AssertionError(
            f"step count mismatch: {len(reference)} vs {len(replayed)}"
        )
    for index, (ref, play) in enumerate(zip(reference, replayed, strict=True)):
        if ref.state.mode != play.state.mode:
            raise AssertionError(f"step {index}: mode mismatch")
        if ref.command.waypoint_index != play.command.waypoint_index:
            raise AssertionError(f"step {index}: waypoint mismatch")
        if not np.allclose(ref.state.pos, play.state.pos, atol=pos_tol_m, rtol=0.0):
            raise AssertionError(f"step {index}: position mismatch")
        if not np.allclose(ref.state.vel, play.state.vel, atol=vel_tol_mps, rtol=0.0):
            raise AssertionError(f"step {index}: velocity mismatch")
        if abs(ref.state.depth_m - play.state.depth_m) > 1e-9:
            raise AssertionError(f"step {index}: depth mismatch")


def save_replay_log(path: Path | str, log: ReplayLog) -> None:
    """Write a replay log to JSON."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(log.to_dict(), indent=2), encoding="utf-8")


def load_replay_log(path: Path | str) -> ReplayLog:
    """Load a replay log from JSON."""
    return ReplayLog.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


__all__ = [
    "ReplayLog",
    "ReplayManifest",
    "assert_replay_matches",
    "build_navigator_from_manifest",
    "load_replay_log",
    "packet_from_dict",
    "packet_to_dict",
    "record_harbor_packets",
    "replay_packets",
    "save_replay_log",
    "step_snapshot",
]
