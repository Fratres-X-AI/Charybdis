"""Multi-agent UUV coordination for Charybdis.

Runs 2-3 vehicles through the shared ``charybdis_core`` engine. Agents exchange
TCM fixes and noisy relative-range measurements when within comm range, then
apply a lightweight consensus update to bound team drift.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from concurrent.futures import ProcessPoolExecutor
import numpy as np

import charybdis_core as core


@dataclass
class SwarmParams:
    n_agents: int = 3
    comm_range: float = 35.0
    range_noise: float = 2.0
    share_tcm: bool = True
    sim_params: core.SimParams = field(default_factory=core.SimParams)


@dataclass
class SwarmState:
    agents: list = field(default_factory=list)
    params: SwarmParams = field(default_factory=SwarmParams)
    shared_fixes: list = field(default_factory=list)


def init_swarm(params: SwarmParams | None = None, seed: int = 0) -> SwarmState:
    p = params or SwarmParams()
    p.sim_params.autonomy = False
    p.sim_params.n_contacts = 0
    rng = np.random.default_rng(seed)
    agents = []
    for i in range(p.n_agents):
        s = core.init_state(seed=int(rng.integers(0, 1_000_000)), params=p.sim_params)
        s.true_pos = core.START + rng.normal(0, 0.5, size=2)
        s.est_pos = s.true_pos + rng.normal(0, 1.0, size=2)
        s.agent_id = i
        agents.append(s)
    return SwarmState(agents=agents, params=p)


def _pairwise_ranges(agents) -> list[tuple[int, int, float]]:
    out = []
    for i, a in enumerate(agents):
        for j in range(i + 1, len(agents)):
            d = float(np.hypot(*(a.true_pos - agents[j].true_pos)))
            out.append((i, j, d))
    return out


def _consensus(agents, i: int, j: int, rng: np.random.Generator, noise: float):
    """Fuse relative range measurement into both beliefs."""
    ai, aj = agents[i], agents[j]
    if float(np.hypot(*(ai.est_pos - aj.est_pos))) > 1e-6:
        return
    rel = aj.est_pos - ai.est_pos
    dist = float(np.hypot(*rel))
    if dist < 1e-6:
        return
    meas = float(np.hypot(*(ai.true_pos - aj.true_pos))) + rng.normal(0, noise)
    direction = rel / dist
    half = 0.5 * (meas - dist) * direction
    ai.est_pos -= half
    aj.est_pos += half


def step_swarm(sw: SwarmState) -> None:
    p = sw.params
    for a in sw.agents:
        core.step(a, p.sim_params)

    rng = sw.agents[0].rng_aux
    for i, j, _ in _pairwise_ranges(sw.agents):
        ai, aj = sw.agents[i], sw.agents[j]
        if float(np.hypot(*(ai.true_pos - aj.true_pos))) <= p.comm_range:
            _consensus(sw.agents, i, j, rng, p.range_noise)

    if p.share_tcm:
        for a in sw.agents:
            for tick, kind, pos in a.fixes:
                if kind == "TCM" and (tick, kind, tuple(pos)) not in sw.shared_fixes:
                    sw.shared_fixes.append((tick, kind, tuple(pos)))
                    for b in sw.agents:
                        if b is not a and float(np.hypot(*(b.est_pos - pos))) < 15:
                            b.est_pos = 0.7 * b.est_pos + 0.3 * pos
                            b.P = np.diag([0.5, 0.5, 1e-4, 1e-4])


def team_cep(sw: SwarmState) -> float:
    errs = [float(np.hypot(*(a.true_pos - a.est_pos))) for a in sw.agents]
    return float(np.percentile(errs, 50))


def _solo_run(args):
    seed, ticks = args
    p = core.SimParams(autonomy=False, n_contacts=0)
    s = core.init_state(seed=seed, params=p)
    for _ in range(ticks):
        core.step(s, p)
    return float(np.hypot(*(s.true_pos - s.est_pos)))


def _swarm_run(args):
    seed, ticks, n = args
    sw = init_swarm(SwarmParams(n_agents=n), seed=seed)
    for _ in range(ticks):
        step_swarm(sw)
    return team_cep(sw)


def montecarlo_compare(n_runs: int = 8, ticks: int = 80, n_agents: int = 3,
                       workers: int = 31) -> dict:
    seeds = list(range(n_runs))
    with ProcessPoolExecutor(max_workers=workers) as ex:
        solo = list(ex.map(_solo_run, [(s, ticks) for s in seeds]))
        team = list(ex.map(_swarm_run, [(s, ticks, n_agents) for s in seeds]))
    return {
        "solo_cep50_m": float(np.percentile(solo, 50)),
        "team_cep50_m": float(np.percentile(team, 50)),
        "improvement_x": float(np.percentile(solo, 50) / max(np.percentile(team, 50), 1e-6)),
    }
