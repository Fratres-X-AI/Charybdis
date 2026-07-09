from dataclasses import replace

import numpy as np
import pytest
from charybdis import SimConfig, Terrain, run_simulation
from charybdis.evaluation import run_montecarlo
from charybdis.legacy import TerrainParticleFilter


def test_pf_unit_predict_update():
    cfg = SimConfig(n_particles=400)
    terrain = Terrain.synthetic(cfg)
    pf = TerrainParticleFilter(cfg, terrain, pos0=[4000.0, 4000.0],
                               vel0=[180.0, 140.0],
                               rng=np.random.default_rng(0))
    pf.predict(np.array([0.1, -0.2]), cfg.dt)
    z = float(terrain.elevation(4000.0, 4000.0))
    pf.update_trn(z)
    assert 0 < pf.neff() <= pf.N
    assert np.all(np.isfinite(pf.pos))
    C = pf.pos_cov()
    assert np.allclose(C, C.T)
    assert np.all(np.linalg.eigvalsh(C) >= -1e-9)


@pytest.mark.slow
def test_pf_competitive_nominal():
    cfg = SimConfig(duration=45.0, n_particles=500)
    res = run_simulation(cfg)
    s = res.summary()
    assert res.pf_err is not None
    assert s["pf_final_m"] < s["ins_final_m"]
    assert s["pf_rmse_m"] < 0.25 * s["ins_rmse_m"]
    assert s["pf_final_m"] < 100.0


@pytest.mark.slow
def test_pf_recovers_large_initial_error():
    """TRN-only with a 450 m initial error: PF converges from a wide prior."""
    base = SimConfig(duration=55.0, init_pos_error=450.0, init_pos_std=500.0,
                     use_tercom=False, n_particles=600)
    for seed in (1, 2):
        s = run_simulation(replace(base, seed=seed)).summary()
        assert s["pf_final_m"] < 0.2 * base.init_pos_error
        assert s["pf_final_m"] < s["ins_final_m"]


@pytest.mark.slow
def test_pmf_recovers_large_initial_error():
    """Marginalized PMF: grid TRN resolves large initial position ambiguity."""
    base = SimConfig(duration=55.0, init_pos_error=450.0, init_pos_std=500.0,
                     use_tercom=False, use_pf=False)
    for seed in (1, 2, 3):
        s = run_simulation(replace(base, seed=seed)).summary()
        assert s["pmf_final_m"] < 0.25 * base.init_pos_error
        assert s["pmf_final_m"] < s["ins_final_m"]


@pytest.mark.slow
def test_montecarlo_cep_and_nees():
    cfg = SimConfig(duration=45.0, n_particles=400)
    mc = run_montecarlo(cfg, n_runs=4)
    assert mc.n_runs == 4
    assert mc.cep("ekf", 50) < mc.cep("ins", 50)
    assert mc.cep("pf", 50) < mc.cep("ins", 50)
    assert mc.cep("ekf", 95) >= mc.cep("ekf", 50)
    assert 0.3 < mc.ekf_nees < 60.0                            # broad consistency band
    assert "CEP50" in mc.table()
