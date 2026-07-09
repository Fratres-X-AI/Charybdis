"""Cooperative multi-agent navigation with OWTT acoustic ranging.

WARNING: Experimental / unstable API. Do not use in production navigation
paths. Import through :mod:`charybdis.experimental`.

Runs multiple ``Navigator`` instances over a shared terrain map. Agents within
comm range exchange one-way-travel-time (OWTT) range measurements and shared
TRN fixes to bound team drift.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, replace
from multiprocessing import Pool

import numpy as np

from ..config import SimConfig
from ..imu import IMU
from ..legacy.navigator import Navigator
from ..parallel import pool_workers
from ..terrain import Terrain
from ..trajectory import generate_truth


@dataclass
class SwarmConfig:
    n_agents: int = 3
    comm_range: float = 8000.0
    owtt_noise: float = 8.0
    share_trn: bool = True
    duration: float = 100.0
    seed: int = 1


@dataclass
class AgentRun:
    nav: Navigator
    imu: IMU
    final_err: float = 0.0


@dataclass
class SwarmResult:
    agents: list[AgentRun]
    owtt_updates: int = 0
    shared_fixes: int = 0


def owtt_range(true_a: np.ndarray, true_b: np.ndarray,
               rng: np.random.Generator, noise: float) -> float:
    d = float(np.linalg.norm(true_a - true_b))
    return d + rng.normal(0.0, noise)


def fuse_owtt_range(nav_a: Navigator, nav_b: Navigator, meas: float,
                    noise: float) -> None:
    pa, pb = nav_a.ekf.pos, nav_b.ekf.pos
    delta = pb - pa
    pred = float(np.linalg.norm(delta))
    if pred < 1e-3:
        return
    H_a = np.array([delta[0] / pred, delta[1] / pred, 0, 0, 0, 0])
    H_b = np.array([-delta[0] / pred, -delta[1] / pred, 0, 0, 0, 0])
    R = noise ** 2
    innov = meas - pred
    for nav, H in ((nav_a, H_a), (nav_b, H_b)):
        S = float(H @ nav.ekf.P @ H + R)
        if S <= 0:
            continue
        K = (nav.ekf.P @ H) / S
        nav.ekf.x = nav.ekf.x + K * innov
        nav.ekf._joseph(H.reshape(1, -1), np.array([[R]]), K.reshape(-1, 1))


def run_swarm(cfg: SwarmConfig | None = None) -> SwarmResult:
    cfg = cfg or SwarmConfig()
    base = SimConfig(duration=cfg.duration, seed=cfg.seed, use_pf=False)
    terrain = Terrain.synthetic(base)
    truth = generate_truth(base, terrain)
    rng = np.random.default_rng(cfg.seed + 909)

    runs: list[AgentRun] = []
    formation = [np.zeros(2)] + [rng.normal(0, 150.0, size=2)
                                   for _ in range(cfg.n_agents - 1)]
    for i in range(cfg.n_agents):
        off = rng.normal(0, 60.0, size=2) if i else np.zeros(2)
        scfg = replace(base, seed=cfg.seed + i)
        pos0 = truth.pos[0] + off
        nav = Navigator(scfg, terrain, pos0, truth.vel[0],
                        rng=np.random.default_rng(cfg.seed + 200 + i))
        imu = IMU(replace(scfg, seed=scfg.seed + 101), terrain)
        runs.append(AgentRun(nav=nav, imu=imu))

    owtt_n = share_n = 0
    for k in range(len(truth)):
        t = truth.t[k]
        tp = truth.pos[k]
        for ar in runs:
            ar.nav.step(ar.imu.sample(truth, k), t)

        if cfg.share_trn and k > 0 and k % 500 == 0:
            best = min(runs, key=lambda a: a.nav.ekf.pos_std.max())
            for ar in runs:
                if ar.nav is not best.nav:
                    ar.nav.ekf.update_position(best.nav.ekf.pos,
                                               np.diag([400.0, 400.0]))
                    share_n += 1

        for i in range(len(runs)):
            ti = tp + formation[i]
            for j in range(i + 1, len(runs)):
                tj = tp + formation[j]
                if float(np.linalg.norm(ti - tj)) <= cfg.comm_range:
                    meas = owtt_range(ti, tj, rng, cfg.owtt_noise)
                    fuse_owtt_range(runs[i].nav, runs[j].nav, meas, cfg.owtt_noise)
                    owtt_n += 1

    for ar in runs:
        ar.final_err = float(np.linalg.norm(ar.nav.ekf.pos - truth.pos[-1]))

    return SwarmResult(agents=runs, owtt_updates=owtt_n, shared_fixes=share_n)


def _solo(args):
    seed, duration = args
    from ..simulation import run_simulation
    return float(run_simulation(
        SimConfig(duration=duration, seed=seed, use_pf=False)).ekf_err[-1])


def _team(args):
    seed, duration, n = args
    r = run_swarm(SwarmConfig(n_agents=n, duration=duration, seed=seed))
    return float(np.median([a.final_err for a in r.agents]))


def montecarlo_swarm(n_runs: int = 16, duration: float = 80.0,
                     n_agents: int = 3, workers: int = 31) -> dict:
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    nw = pool_workers(workers)
    seeds = list(range(1, n_runs + 1))
    with Pool(processes=nw) as pool:
        solo = pool.map(_solo, [(s, duration) for s in seeds])
        team = pool.map(_team, [(s, duration, n_agents) for s in seeds])
    s50 = float(np.percentile(solo, 50))
    t50 = float(np.percentile(team, 50))
    return {"solo_cep50_m": s50, "team_cep50_m": t50,
            "improvement_x": s50 / max(t50, 1e-6)}
