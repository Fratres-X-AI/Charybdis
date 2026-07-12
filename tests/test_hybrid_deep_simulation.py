import pytest
from charybdis.hybrid import NavMode
from charybdis.simulation import HybridDeepConfig, run_hybrid_deep_simulation


@pytest.mark.slow
def test_hybrid_deep_simulation_runs_surface_to_1000m():
    res = run_hybrid_deep_simulation(HybridDeepConfig(seed=4))
    s = res.summary()

    assert s["route_complete"]
    assert s["used_surface"]
    assert s["used_submerged"]
    assert s["last_gps_t"] is not None
    assert s["last_bathy_t"] is not None
    assert float(res.truth_depth.max()) >= 900.0
    assert s["final_depth_error_m"] < 6.0
    assert res.modes[0] == NavMode.SURFACE
    assert res.modes[-1] == NavMode.SURFACE
    assert NavMode.SUBMERGED in res.modes


def test_hybrid_deep_simulation_is_deterministic_for_seed():
    cfg = HybridDeepConfig(seed=9)
    a = run_hybrid_deep_simulation(cfg).summary()
    b = run_hybrid_deep_simulation(cfg).summary()

    assert a == b
