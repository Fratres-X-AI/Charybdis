import os

import numpy as np
import pytest

import charybdis_core as core


def test_tcm_recovers_offset():
    """Cross-correlation must recover the est->true offset near a node."""
    true = core.ANOMALIES["TRENCH ALPHA"] + np.array([1.5, -1.0])
    est = true + np.array([4.0, -3.0])            # dead-reckoning error
    corrected, peak, surf = core.tcm_cross_correlation(true, est)
    assert peak > 0.9
    assert np.linalg.norm(corrected - true) < 1.0
    assert surf.shape[0] == surf.shape[1]


def test_covariance_grows_then_resets_on_fix():
    p = core.SimParams(drift=15.0)
    s = core.init_state(seed=1)
    r0 = core.error_radius(s.P)
    for _ in range(12):                            # stay clear of any node
        core.step(s, p)
    assert not s.fixes
    grown = core.error_radius(s.P)
    assert grown > r0
    core.request_ping(s)
    core.step(s, p)
    assert core.error_radius(s.P) < 0.05          # flattened by the fix
    assert s.ping_ticks > 0
    assert "COMPROMISED" in s.ew_state


def test_error_radius_tracks_actual_deflection():
    """1-sigma radius should be the right order of magnitude vs true error."""
    p = core.SimParams()
    s = core.init_state(seed=3)
    for _ in range(60):
        core.step(s, p)
    defl = np.hypot(*(s.true_pos - s.est_pos))
    r = core.error_radius(s.P)
    assert 0.2 * r <= defl + 1e-6 <= 6.0 * r + 3.0


def test_tcm_fires_and_bounds_error():
    p = core.SimParams()
    s = core.init_state(seed=7)
    while not s.reached and s.tick < 400:
        core.step(s, p)
    assert s.reached
    kinds = {k for _, k, _ in s.fixes}
    assert "TCM" in kinds                          # at least one contour lock
    # every automatic TCM fix must bound the estimate close to a real node
    for _, kind, pos in s.fixes:
        if kind == "TCM":
            d = min(np.linalg.norm(pos - c) for c in core.ANOMALIES.values())
            assert d < core.TCM_RADIUS + 2.0


def test_ping_forces_immediate_fix():
    p = core.SimParams(drift=20.0)
    s = core.init_state(seed=5)
    for _ in range(15):
        core.step(s, p)
    core.request_ping(s)
    core.step(s, p)
    assert np.linalg.norm(s.true_pos - s.est_pos) < 1e-6
    assert s.fixes[-1][1] == "PING"


def test_streamlit_console_renders_without_exception():
    at = pytest.importorskip("streamlit.testing.v1")
    os.environ["CHARYBDIS_NO_LOOP"] = "1"
    app = at.AppTest.from_file("charybdis_console.py", default_timeout=30)
    app.run()
    assert not app.exception
    # advance the sim and re-render to exercise chart/log/ellipse paths
    core_state = app.session_state["sim"]
    for _ in range(40):
        core.step(core_state, core.SimParams())
    app.run()
    assert not app.exception
    os.environ.pop("CHARYBDIS_NO_LOOP", None)
