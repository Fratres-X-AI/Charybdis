from charybdis import (HybridHarborConfig, NavMode,
                       run_hybrid_harbor_simulation)


def test_hybrid_harbor_simulation_runs_surface_submerged_surface():
    res = run_hybrid_harbor_simulation(HybridHarborConfig(seed=4))
    s = res.summary()

    assert s["route_complete"]
    assert s["used_surface"]
    assert s["used_submerged"]
    assert s["last_gps_t"] is not None
    assert s["last_bathy_t"] is not None
    assert s["final_error_m"] < 8.0
    assert s["final_depth_error_m"] < 0.5
    assert res.modes[0] == NavMode.SURFACE
    assert res.modes[-1] == NavMode.SURFACE
    assert NavMode.SUBMERGED in res.modes


def test_hybrid_harbor_simulation_is_deterministic_for_seed():
    cfg = HybridHarborConfig(seed=9)
    a = run_hybrid_harbor_simulation(cfg).summary()
    b = run_hybrid_harbor_simulation(cfg).summary()

    assert a == b
