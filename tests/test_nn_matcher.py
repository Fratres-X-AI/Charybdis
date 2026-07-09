import numpy as np
import pytest
from charybdis import SimConfig, Terrain


def test_so2_model_forward():
    torch = pytest.importorskip("torch")
    from charybdis.experimental.nn_matcher import build_model, extract_patch

    model = build_model()
    cfg = SimConfig(seed=1)
    terr = Terrain.synthetic(cfg)
    obs = extract_patch(np.array([5000.0, 5000.0]), terr)
    mp = extract_patch(np.array([5100.0, 5100.0]), terr)
    t_o = torch.from_numpy(obs[None].astype(np.float32))
    t_m = torch.from_numpy(mp[None].astype(np.float32))
    off, suit = model(t_o, t_m)
    assert off.shape == (1, 2)
    assert suit.shape == (1,)
    assert 0.0 <= float(suit[0]) <= 1.0


def test_match_position_cpu():
    pytest.importorskip("torch")
    from charybdis.experimental.nn_matcher import match_position

    cfg = SimConfig(seed=2)
    terr = Terrain.synthetic(cfg)
    true = np.array([8000.0, 8000.0])
    est = true + np.array([50.0, -30.0])
    pos, suit = match_position(true, est, terr)
    assert pos.shape == (2,)
    assert np.isfinite(suit)
