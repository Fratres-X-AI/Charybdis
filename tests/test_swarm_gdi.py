import os
import sys

import numpy as np
import pytest

from charybdis.swarm import SwarmConfig, montecarlo_swarm, run_swarm


def test_swarm_runs():
    r = run_swarm(SwarmConfig(n_agents=3, duration=15.0, seed=3))
    assert len(r.agents) == 3
    assert r.owtt_updates > 0
    errs = [a.final_err for a in r.agents]
    assert np.mean(errs) < 200.0


@pytest.mark.skipif(os.environ.get("GITHUB_ACTIONS") == "true",
                    reason="slow MC; validated on pod")
def test_swarm_montecarlo():
    m = montecarlo_swarm(n_runs=2, duration=25.0, workers=1)
    assert m["solo_cep50_m"] > 0
    assert m["team_cep50_m"] > 0
