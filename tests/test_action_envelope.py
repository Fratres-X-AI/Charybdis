"""Tests for continuous action authority (ActionEnvelope)."""

from charybdis.action_envelope import ACTIONS, ActionEnvelope, compute_action_envelope
from charybdis.config import SimConfig
from charybdis.imu import IMU
from charybdis.legacy import Navigator
from charybdis.terrain import Terrain
from charybdis.trajectory import generate_truth


def _run_nav(steps: int = 30, **cfg_kw) -> Navigator:
    cfg = SimConfig(duration=steps * 0.02, seed=11, **cfg_kw)
    terrain = Terrain.synthetic(cfg)
    truth = generate_truth(cfg, terrain)
    nav = Navigator(cfg, terrain, truth.pos[0], truth.vel[0])
    imu = IMU(cfg, terrain)
    for k in range(1, min(steps, len(truth) - 1)):
        nav.step(imu.sample(truth, k), k * cfg.dt)
    return nav


def test_action_envelope_scores_in_unit_interval():
    nav = _run_nav()
    env = nav.action_envelope()
    assert isinstance(env, ActionEnvelope)
    assert set(env.permitted) == set(ACTIONS)
    for score in env.permitted.values():
        assert 0.0 <= score <= 1.0
    assert 0.0 <= env.confidence <= 1.0
    assert env.pos_err_1sigma > 0.0


def test_high_threat_reduces_go_dark_and_active_acoustic():
    nav = _run_nav()
    calm = nav.action_envelope(threat=0.0)
    hot = nav.action_envelope(threat=3.0)
    assert hot.permitted["go_dark"] <= calm.permitted["go_dark"]
    assert hot.permitted["active_acoustic"] <= calm.permitted["active_acoustic"]


def test_compute_action_envelope_matches_navigator_method():
    nav = _run_nav(steps=15, use_pmf=False)
    terrain = nav.terrain
    a = nav.action_envelope(t=0.3)
    b = compute_action_envelope(nav, terrain, t=0.3)
    assert a.confidence == b.confidence
    assert a.permitted == b.permitted


def test_best_action_and_allows():
    nav = _run_nav(steps=50)
    env = nav.action_envelope()
    best = env.best_action(threshold=0.0)
    assert best in ACTIONS
    assert env.allows(best, threshold=0.0)
