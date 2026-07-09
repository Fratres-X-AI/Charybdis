"""Tests for the Charybdis autonomy / realism upgrade.

Covers: real-bathymetry loading, the Janus DVL + IMU sensor models, multi-contact
tracking, the mission FSM, endurance/RTB, adaptive terrain fixing, active-acoustic
management, reactive terrain avoidance, and spoof-resistant TCM gating.
"""

import numpy as np
import pytest
from console import charybdis_bathy as bathy
from console import charybdis_core as core
from console import charybdis_sensors as sensors
from console import charybdis_tracking as tracking

pytestmark = pytest.mark.console


def _run(params, seed=7, cap=600):
    s = core.init_state(seed=seed, params=params)
    while not s.reached and s.tick < cap:
        core.step(s, params)
    return s


# --------------------------------------------------------------------------- #
#  REAL BATHYMETRY LOADING
# --------------------------------------------------------------------------- #
def test_bathymetry_loader_roundtrip(tmp_path):
    grid = bathy.sample_synthetic_to_grid(core._synthetic_bathymetry, n=240)
    pts = np.array([[10.0, 12.0], [55.0, 40.0], [100.0, 105.0]])
    for x, y in pts:
        assert abs(float(grid(x, y)) - float(core._synthetic_bathymetry(x, y))) < 1.5

    p = tmp_path / "seabed.npz"
    np.savez(p, z=grid.z, extent=np.array([-10.0, 135.0, -10.0, 135.0]))
    loaded = bathy.load_bathymetry(str(p))
    assert abs(float(loaded(55.0, 40.0)) - float(grid(55.0, 40.0))) < 1e-6

    try:
        core.set_bathymetry(loaded)
        assert (
            abs(float(core.bathymetry(55.0, 40.0)) - float(loaded(55.0, 40.0))) < 1e-9
        )
    finally:
        core.reset_bathymetry()
    assert core.bathymetry(55.0, 40.0) == core._synthetic_bathymetry(55.0, 40.0)


# --------------------------------------------------------------------------- #
#  DVL / IMU SENSOR MODELS
# --------------------------------------------------------------------------- #
def test_dvl_beam_reconstruction_exact_when_clean():
    p = core.SimParams(dvl=0.0, dvl_scale=0.0, dvl_dropout=0.0)
    rng = np.random.default_rng(0)
    v = np.array([1.2, -0.4])
    r = sensors.dvl_beam_measure(v, p, rng)
    assert r.n_good == 4 and r.quality == 1.0
    assert np.allclose(r.velocity, v, atol=1e-9)


def test_dvl_full_dropout_loses_bottom_lock():
    p = core.SimParams(dvl_dropout=1.0)
    r = sensors.dvl_beam_measure(np.array([1.0, 1.0]), p, np.random.default_rng(0))
    assert r.quality == 0.0 and r.n_good == 0


def test_imu_heading_bias_walks():
    p = core.SimParams(drift=15.0)
    rng = np.random.default_rng(1)
    b = 0.0
    for _ in range(50):
        b = sensors.imu_heading_bias_walk(b, p, rng)
    assert abs(b) > 1e-3  # accumulated a non-trivial heading error


# --------------------------------------------------------------------------- #
#  MULTI-CONTACT TRACKING
# --------------------------------------------------------------------------- #
def test_contact_tracker_converges():
    rng = np.random.default_rng(0)
    w = tracking.spawn(3, rng)
    ids = {c.cid for c in w.contacts}
    assert len(ids) == 3
    own = np.array([60.0, 60.0])
    for _ in range(60):
        tracking.step(w, own, 1.0, rng)
    err = tracking.track_error(w)
    assert 0.0 < err < 3.0  # trackers lock the noisy contacts


# --------------------------------------------------------------------------- #
#  MISSION FSM / ENDURANCE / TRACKING END-TO-END
# --------------------------------------------------------------------------- #
def test_autonomous_mission_completes_and_inspects():
    p = core.SimParams(autonomy=True)
    seen = set()
    s = core.init_state(seed=7, params=p)
    while not s.reached and s.tick < 600:
        core.step(s, p)
        seen.add(s.mission_state)
    assert s.reached
    assert {"PATROL", "INSPECT"} <= seen
    assert s.mission_state == "ON STATION"
    assert s.energy_frac < 1.0
    assert any(k == "TCM" for _, k, _ in s.fixes)
    assert s.world is not None and tracking.track_error(s.world) < 5.0


def test_low_endurance_forces_rtb():
    p = core.SimParams(autonomy=True, endurance=45.0)  # drains fast
    seen = set()
    s = core.init_state(seed=7, params=p)
    while not s.reached and s.tick < 800:
        core.step(s, p)
        seen.add(s.mission_state)
    assert "RTB" in seen
    base = core.START
    assert float(np.hypot(*(s.true_pos - base))) < core.START.size + 5.0 or s.reached


# --------------------------------------------------------------------------- #
#  ADAPTIVE TCM + ACTIVE-ACOUSTIC MANAGEMENT
# --------------------------------------------------------------------------- #
def test_adaptive_tcm_diverts_when_uncertain():
    p = core.SimParams(autonomy=True, drift=30.0, tcm_trigger=12.0, acoustic_mgmt=False)
    seen = set()
    s = core.init_state(seed=3, params=p)
    while not s.reached and s.tick < 800:
        core.step(s, p)
        seen.add(s.mission_state)
    assert "TCM FIX" in seen
    assert any(k == "TCM" for _, k, _ in s.fixes)


def test_active_acoustic_policy_threat_gated():
    from console import charybdis_autonomy as autonomy

    hot = core.SimParams(
        autonomy=True, acoustic_mgmt=True, active_ping_trigger=20.0, threat_level=0.2
    )
    cold = core.SimParams(
        autonomy=True, acoustic_mgmt=True, active_ping_trigger=20.0, threat_level=0.95
    )
    s = core.init_state(seed=0, params=hot)
    s.P = np.diag([900.0, 900.0, 1.0, 1.0])  # 1-sigma error = 30 m > trigger
    assert autonomy.wants_active_ping(s, hot)  # lost + benign -> radiate
    assert not autonomy.wants_active_ping(s, cold)  # lost + hostile -> stay silent
    s.P = np.diag([16.0, 16.0, 1.0, 1.0])  # error 4 m < trigger
    assert not autonomy.wants_active_ping(s, hot)  # confident -> stay silent
    assert not autonomy.wants_active_ping(s, core.SimParams(autonomy=False))


def test_active_acoustic_fix_applied_in_step():
    p = core.SimParams(
        autonomy=True,
        adaptive_tcm=False,
        acoustic_mgmt=True,
        active_ping_trigger=20.0,
        threat_level=0.2,
    )
    s = core.init_state(seed=0, params=p)
    s.P = np.diag([900.0, 900.0, 1.0, 1.0])
    core.step(s, p)
    assert s.fixes and s.fixes[-1][1] == "PING"
    assert s.acoustic_mode == "ACTIVE"
    assert core.error_radius(s.P) < 0.05  # fix flattened the covariance


# --------------------------------------------------------------------------- #
#  REACTIVE TERRAIN AVOIDANCE
# --------------------------------------------------------------------------- #
def test_terrain_avoidance_keeps_clearance():
    p = core.SimParams(autonomy=True)
    saw_avoid = False
    min_alt = np.inf
    s = core.init_state(seed=7, params=p)
    while not s.reached and s.tick < 600:
        core.step(s, p)
        saw_avoid |= s.avoid_active
        min_alt = min(min_alt, s.altitude)
    assert min_alt > 0.0  # never grounded
    assert saw_avoid  # reacted to rising terrain (ridge / seamount)


# --------------------------------------------------------------------------- #
#  SPOOF RESISTANCE
# --------------------------------------------------------------------------- #
def test_spoof_is_detected_and_rejected():
    ridge = core.ANOMALIES["RIDGE BRAVO"]
    p = core.SimParams(
        autonomy=True,
        adaptive_tcm=False,
        acoustic_mgmt=False,
        spoof=True,
        spoof_center=tuple(ridge),
        spoof_radius=12.0,
        spoof_amp=45.0,
    )
    s = _run(p, seed=7)
    assert s.spoof_detected
    accepted_near_ridge = [
        pos for _, k, pos in s.fixes if k == "TCM" and np.hypot(*(pos - ridge)) < 8.0
    ]
    assert not accepted_near_ridge
    # other genuine contours still lock
    assert any(k == "TCM" for _, k, _ in s.fixes)


def test_no_spoof_locks_all_contours():
    p = core.SimParams(autonomy=True, adaptive_tcm=False, acoustic_mgmt=False)
    s = _run(p, seed=7)
    assert not s.spoof_detected
    assert sum(1 for _, k, _ in s.fixes if k == "TCM") >= 2
