"""Tests for realistic sensors, vehicle plant, frames, and match health."""

from __future__ import annotations

import numpy as np
import pytest
from charybdis.hybrid.bathymetry import (
    BathymetryMap,
    BathymetryProfile,
    MatchStatus,
    TerrainMatchMonitor,
    TerrainProfileMatcher,
)
from charybdis.hybrid.frames import (
    body_to_nav,
    compensate_measurement_latency,
    nav_to_body,
    wrap_pi,
)
from charybdis.hybrid.fusion import HybridSensorFusion, NavDegradationLevel
from charybdis.hybrid.modes import NavMode
from charybdis.hybrid.patrol import PatrolCommand
from charybdis.hybrid.sensor_plant import SensorPlant, SensorPlantConfig
from charybdis.hybrid.sensors import ImuMeasurement, SensorPacket
from charybdis.hybrid.vehicle import VehiclePlant, VehiclePlantConfig, VehicleState
from charybdis.simulation.deep import (
    HybridDeepConfig,
    build_navigation_chart_map,
    build_synthetic_deep_map,
    run_hybrid_deep_simulation,
)


def test_frame_conventions_are_consistent() -> None:
    heading = np.deg2rad(30.0)
    body = np.array([1.0, 0.0])
    nav = body_to_nav(body, heading)
    recovered = nav_to_body(nav, heading)
    assert recovered == pytest.approx(body)
    assert wrap_pi(np.pi + 0.1) == pytest.approx(-np.pi + 0.1)


def test_latency_compensation_extrapolates_forward() -> None:
    value = np.array([0.0, 0.0])
    vel = np.array([1.0, 0.0])
    adjusted = compensate_measurement_latency(
        value,
        vel,
        measurement_time_s=1.0,
        filter_time_s=1.5,
    )
    assert adjusted == pytest.approx(np.array([0.5, 0.0]))


def test_sensor_plant_applies_bias_walk_and_depth_lag() -> None:
    plant = SensorPlant(SensorPlantConfig(seed=3))
    depth_samples = []
    for step in range(40):
        depth_samples.append(
            plant.depth(
                true_depth_m=10.0 if step < 20 else 30.0,
                dt=1.0,
                timestamp_s=float(step + 1),
            ).depth_m
        )
    assert plant.state.accel_bias.shape == (2,)
    assert abs(float(np.mean(plant.state.accel_bias))) > 0.0
    assert depth_samples[25] < 30.0


def test_sensor_plant_can_emit_gps_outliers() -> None:
    plant = SensorPlant(
        SensorPlantConfig(gps_outlier_prob=1.0, gps_outlier_scale_m=50.0, seed=2)
    )
    gps = plant.gps(
        np.zeros(2),
        np.zeros(2),
        timestamp_s=1.0,
    )
    assert float(np.linalg.norm(gps.pos)) >= 40.0


def test_vehicle_plant_tracks_heading_and_surge() -> None:
    plant = VehiclePlant(
        VehicleState(
            pos=np.zeros(2),
            vel=np.zeros(2),
            heading_rad=0.0,
            depth_m=0.0,
        ),
        VehiclePlantConfig(surge_tau_s=2.0, heading_rate_max_radps=np.deg2rad(30.0)),
    )
    command = PatrolCommand(
        target_pos=np.array([100.0, 0.0]),
        desired_vel=np.array([1.5, 0.0]),
        desired_heading_rad=np.deg2rad(90.0),
        target_depth_m=20.0,
        target_mode=NavMode.SUBMERGED,
        waypoint_index=0,
    )
    state = plant.step(command, 1.0)
    assert state.speed_mps > 0.0
    assert state.heading_rad > 0.0
    assert state.depth_m > 0.0


def test_match_monitor_rejects_stale_chart() -> None:
    truth_map = build_synthetic_deep_map(seed=1)
    chart_map = build_navigation_chart_map(truth_map, stale_offset_m=(12.0, 0.0))
    matcher = TerrainProfileMatcher(chart_map)
    monitor = TerrainMatchMonitor(
        map_resolution_m=chart_map.resolution_m,
        stale_chart_offset_m=(12.0, 0.0),
    )
    offsets = np.array([[-15.0, 0.0], [0.0, 0.0], [15.0, 0.0]])
    pos = np.array([300.0, 0.0])
    profile = BathymetryProfile(
        offsets,
        truth_map.sample(pos + offsets),
        variance_m2=0.1,
    )
    raw = matcher.match(profile, prior_pos=pos, prior_cov=np.diag([5.0, 5.0]) ** 2)
    assessed = monitor.assess(raw, profile)
    assert assessed.status == MatchStatus.STALE_CHART
    assert assessed.health is not None
    assert assessed.health.degraded


def test_match_monitor_flags_resolution_mismatch() -> None:
    bathymetry_map = BathymetryMap(np.full((40, 40), 120.0), resolution_m=30.0)
    offsets = np.array([[0.0, 0.0], [10.0, 0.0], [20.0, 0.0]])
    profile = BathymetryProfile(
        offsets,
        np.full(3, 120.0) + np.array([0.0, 2.0, 4.0]),
        variance_m2=0.1,
    )
    monitor = TerrainMatchMonitor(map_resolution_m=30.0)
    assessed = monitor.assess(
        TerrainProfileMatcher(bathymetry_map).match(
            profile,
            prior_pos=np.array([20.0, 20.0]),
            prior_cov=np.eye(2) * 25.0,
        ),
        profile,
    )
    assert assessed.status == MatchStatus.MAP_RESOLUTION_MISMATCH


def test_fusion_enters_degraded_mode_when_bathy_untrusted() -> None:
    fusion = HybridSensorFusion([0.0, 0.0])
    fusion.step(
        SensorPacket(
            imu=ImuMeasurement([0.0, 0.0], 1.0, timestamp_s=1.0),
            timestamp_s=1.0,
        )
    )
    from charybdis.hybrid.bathymetry import MatchHealth

    state = fusion.step(
        SensorPacket(
            imu=ImuMeasurement([0.0, 0.0], 1.0, timestamp_s=2.0),
            bathy_health=MatchHealth(
                confidence=0.1,
                trusted=False,
                consecutive_failures=3,
                degraded=True,
            ),
            timestamp_s=2.0,
        )
    )
    assert state.degradation_level == NavDegradationLevel.DEGRADED
    assert not state.diagnostics.bathy_trusted


def test_deep_simulation_runs_with_realistic_plant() -> None:
    result = run_hybrid_deep_simulation(
        HybridDeepConfig(seed=5, max_steps=120, use_realistic_plant=True)
    )
    summary = result.summary()
    assert summary["steps"] > 0
    assert "final_degradation_level" in summary
    assert "final_bathy_confidence" in summary
