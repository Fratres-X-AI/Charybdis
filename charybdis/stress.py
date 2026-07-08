"""Stress-test harness: adversarial terrain, fault injection, Monte-Carlo gates.

Designed for pod-scale evaluation (31 workers, 1000+ seeds) with pass/fail
gates on CEP, divergence rate, and filter consistency (NEES).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from multiprocessing import Pool
from typing import Callable

import numpy as np

from .config import SimConfig
from .evaluate import FILTERS, MonteCarloResult, _nees_second_half
from .simulation import run_simulation
from .terrain import Terrain


def adversarial_terrain(cfg: SimConfig) -> Terrain:
    """Parallel ridges over a flat floor — multimodal terrain correlation."""
    n = int(cfg.terrain_size / cfg.terrain_res) + 1
    xs = np.linspace(0.0, cfg.terrain_size, n)
    ys = np.linspace(0.0, cfg.terrain_size, n)
    gx, gy = np.meshgrid(xs, ys)
    period = 1800.0
    z = 8.0 + 0.35 * cfg.terrain_relief * (
        np.sin(2 * np.pi * gx / period) + np.sin(2 * np.pi * gy / period))
    z += 0.08 * cfg.terrain_relief * np.sin(2 * np.pi * (gx + gy) / (period * 0.7))
    return Terrain(grid=z.astype(np.float64), res=cfg.terrain_res)


@dataclass
class StressGates:
    """Pass/fail thresholds for a stress scenario."""
    ekf_cep95_max_m: float = 120.0
    pmf_cep95_max_m: float = 150.0
    pf_cep95_max_m: float = 150.0
    ins_cep95_max_m: float = 5000.0
    ekf_nees_max: float = 30.0
    pmf_nees_min: float = 0.05
    pmf_nees_max: float = 10.0
    divergence_m: float = 150.0
    max_div_rate: float = 0.05


@dataclass
class StressCase:
    name: str
    cfg: SimConfig
    terrain_fn: Callable[[SimConfig], Terrain] = Terrain.synthetic
    gates: StressGates = field(default_factory=StressGates)
    required: bool = True


def default_stress_cases() -> list[StressCase]:
    base = SimConfig(duration=100.0, n_particles=800)
    return [
        StressCase("nominal", replace(base, use_tercom=True)),
        StressCase("trn_only", replace(base, use_tercom=False)),
        StressCase("large_init", replace(base, use_tercom=False, use_pf=False,
                                          init_pos_error=450.0, init_pos_std=500.0),
                   gates=StressGates(pmf_cep95_max_m=120.0, ekf_cep95_max_m=150.0)),
        StressCase("imu_fault", replace(base, use_tercom=False,
                                         accel_bias_rw=0.015, accel_noise=0.20),
                   gates=StressGates(ekf_cep95_max_m=200.0, pmf_cep95_max_m=200.0)),
        StressCase("featureless", replace(base, use_tercom=False, terrain_relief=8.0),
                   gates=StressGates(ekf_cep95_max_m=250.0, pmf_cep95_max_m=250.0),
                   required=False),
        StressCase("adversarial", replace(base, use_tercom=False, use_pf=False),
                   terrain_fn=adversarial_terrain,
                   gates=StressGates(pmf_cep95_max_m=180.0, ekf_cep95_max_m=200.0)),
    ]


def _run_one(args: tuple) -> MonteCarloResult:
    case_name, seed, cfg_dict, terrain_kind = args
    cfg = SimConfig(**cfg_dict)
    terrain_fn = adversarial_terrain if terrain_kind == "adversarial" else Terrain.synthetic
    if terrain_kind == "featureless":
        cfg = replace(cfg, terrain_relief=8.0)
    res = run_simulation(cfg, terrain=terrain_fn(cfg))
    out = {"case": case_name, "seed": seed}
    for f in FILTERS:
        err = getattr(res, f"{f}_err", None)
        if err is None and f == "ins":
            err = res.ins_err
        if err is None:
            continue
        out[f"{f}_final"] = float(err[-1])
        out[f"{f}_rmse"] = float(np.sqrt(np.mean(err ** 2)))
    out["ekf_nees"] = float(np.mean(
        _nees_second_half(res.ekf_pos, res.ekf_pcov, res.truth.pos)))
    if res.pmf_err is not None:
        out["pmf_nees"] = float(np.mean(
            _nees_second_half(res.pmf_pos, res.pmf_pcov, res.truth.pos)))
    return out


def _aggregate(rows: list[dict], n_runs: int) -> MonteCarloResult:
    final = {f: [] for f in FILTERS}
    rmse = {f: [] for f in FILTERS}
    nees_all, pmf_nees_all = [], []
    for r in rows:
        for f in FILTERS:
            kf, kr = f"{f}_final", f"{f}_rmse"
            if kf in r:
                final[f].append(r[kf])
                rmse[f].append(r[kr])
        if "ekf_nees" in r:
            nees_all.append(r["ekf_nees"])
        if "pmf_nees" in r:
            pmf_nees_all.append(r["pmf_nees"])
    final = {f: np.array(v) for f, v in final.items() if v}
    rmse = {f: np.array(v) for f, v in rmse.items() if v}
    seeds = [r["seed"] for r in rows]
    return MonteCarloResult(
        n_runs=n_runs, seeds=seeds, final_err=final, rmse=rmse,
        ekf_nees=float(np.mean(nees_all)) if nees_all else 0.0,
        pmf_nees=float(np.mean(pmf_nees_all)) if pmf_nees_all else 0.0,
    )


def evaluate_gates(mc: MonteCarloResult, gates: StressGates) -> dict[str, bool]:
    """Return per-gate pass/fail booleans."""
    div = gates.divergence_m
    out: dict[str, bool] = {}
    if "ekf" in mc.final_err:
        out["ekf_cep95"] = mc.cep("ekf", 95) <= gates.ekf_cep95_max_m
        out["ekf_nees"] = mc.ekf_nees <= gates.ekf_nees_max
        out["ekf_div"] = float(np.mean(mc.final_err["ekf"] > div)) <= gates.max_div_rate
    if "pmf" in mc.final_err:
        out["pmf_cep95"] = mc.cep("pmf", 95) <= gates.pmf_cep95_max_m
        out["pmf_nees"] = gates.pmf_nees_min <= mc.pmf_nees <= gates.pmf_nees_max
        out["pmf_div"] = float(np.mean(mc.final_err["pmf"] > div)) <= gates.max_div_rate
    if "pf" in mc.final_err:
        out["pf_cep95"] = mc.cep("pf", 95) <= gates.pf_cep95_max_m
        out["pf_div"] = float(np.mean(mc.final_err["pf"] > div)) <= gates.max_div_rate
    if "ins" in mc.final_err:
        out["ins_cep95"] = mc.cep("ins", 95) <= gates.ins_cep95_max_m
    return out


@dataclass
class StressResult:
    case: str
    mc: MonteCarloResult
    gates: dict[str, bool]
    required: bool = True

    @property
    def passed(self) -> bool:
        return all(self.gates.values()) if self.gates else False


def run_stress_case(case: StressCase, seeds: list[int] | None = None,
                    n_workers: int = 31) -> StressResult:
    seeds = seeds or list(range(1, 65))
    terrain_kind = "synthetic"
    if case.name == "adversarial":
        terrain_kind = "adversarial"
    elif case.name == "featureless":
        terrain_kind = "featureless"
    cfg_dict = {f.name: getattr(case.cfg, f.name)
                for f in case.cfg.__dataclass_fields__.values()}
    jobs = [(case.name, s, cfg_dict, terrain_kind) for s in seeds]
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    with Pool(processes=n_workers) as pool:
        rows = pool.map(_run_one, jobs)
    mc = _aggregate(rows, len(seeds))
    gates = evaluate_gates(mc, case.gates)
    return StressResult(case=case.name, mc=mc, gates=gates, required=case.required)


def run_stress_harness(cases: list[StressCase] | None = None,
                       seeds: list[int] | None = None,
                       n_workers: int = 31) -> list[StressResult]:
    cases = cases or default_stress_cases()
    return [run_stress_case(c, seeds=seeds, n_workers=n_workers) for c in cases]


def stress_report(results: list[StressResult]) -> str:
    lines = ["Charybdis stress harness report"]
    for r in results:
        status = "PASS" if r.passed else ("INFO" if not r.required else "FAIL")
        lines.append(f"\n=== {r.case} [{status}] ===")
        lines.append(r.mc.table())
        for gate, ok in sorted(r.gates.items()):
            lines.append(f"  {gate}: {'OK' if ok else 'FAIL'}")
    n_pass = sum(1 for r in results if r.passed and r.required)
    n_req = sum(1 for r in results if r.required)
    lines.append(f"\nOverall: {n_pass}/{n_req} required scenarios passed")
    return "\n".join(lines)
