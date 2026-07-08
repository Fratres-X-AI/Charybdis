from dataclasses import replace

import pytest

from charybdis.stress import (default_stress_cases, evaluate_gates, run_stress_case,
                              run_stress_harness, stress_report)


@pytest.mark.slow
def test_stress_case_runs_and_reports():
    case = next(c for c in default_stress_cases() if c.name == "trn_only")
    case = replace(case, sim=replace(case.sim, duration=35.0, n_particles=400))
    r = run_stress_case(case, seeds=[1, 2], n_workers=1)
    assert r.mc.n_runs == 2
    assert "ekf" in r.mc.final_err
    assert "pmf" in r.mc.final_err
    assert isinstance(r.gates, dict)
    assert len(r.gates) > 0


@pytest.mark.slow
def test_stress_harness_subset():
    cases = []
    for c in default_stress_cases():
        if c.name in ("nominal", "large_init"):
            cases.append(replace(c, sim=replace(c.sim, duration=30.0, n_particles=400)))
    results = run_stress_harness(cases, seeds=[1, 2], n_workers=1)
    assert len(results) == 2
    text = stress_report(results)
    assert "nominal" in text
    assert "large_init" in text


def test_evaluate_gates_structure():
    from charybdis.evaluate import MonteCarloResult
    from charybdis.stress import StressGates
    import numpy as np
    mc = MonteCarloResult(
        n_runs=2, seeds=[1, 2],
        final_err={"ekf": np.array([10.0, 20.0]), "pmf": np.array([15.0, 25.0])},
        rmse={"ekf": np.array([12.0, 22.0]), "pmf": np.array([17.0, 27.0])},
        ekf_nees=3.0, pmf_nees=1.5,
    )
    gates = evaluate_gates(mc, StressGates())
    assert gates["ekf_cep95"] is True
    assert gates["pmf_nees"] is True
