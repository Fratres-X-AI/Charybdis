"""Stress-test harness: adversarial terrain, fault injection, Monte-Carlo gates.

Designed for pod-scale evaluation (31 workers, 1000+ seeds) with pass/fail
gates on CEP, divergence rate, and filter consistency (NEES).
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from multiprocessing import Pool

import numpy as np

from ..config import SimConfig
from ..parallel import pool_workers
from ..simulation import run_simulation
from ..terrain import Terrain
from .evaluate import FILTERS, MonteCarloResult, _nees_second_half


def adversarial_terrain(cfg: SimConfig) -> Terrain:
    """Parallel ridges over a flat floor — multimodal terrain correlation."""
    n = int(cfg.terrain_size / cfg.terrain_res) + 1
    xs = np.linspace(0.0, cfg.terrain_size, n)
    ys = np.linspace(0.0, cfg.terrain_size, n)
    gx, gy = np.meshgrid(xs, ys)
    period = 1800.0
    z = 8.0 + 0.35 * cfg.terrain_relief * (
        np.sin(2 * np.pi * gx / period) + np.sin(2 * np.pi * gy / period)
    )
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
    pf_nees_min: float = 0.05
    pf_nees_max: float = 20.0
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
        StressCase(
            "large_init",
            replace(
                base,
                use_tercom=False,
                use_pf=False,
                init_pos_error=450.0,
                init_pos_std=500.0,
            ),
            gates=StressGates(pmf_cep95_max_m=120.0, ekf_cep95_max_m=150.0),
        ),
        StressCase(
            "imu_fault",
            replace(base, use_tercom=False, accel_bias_rw=0.015, accel_noise=0.20),
            gates=StressGates(ekf_cep95_max_m=200.0, pmf_cep95_max_m=200.0),
        ),
        StressCase(
            "featureless",
            replace(base, use_tercom=False, terrain_relief=8.0),
            gates=StressGates(ekf_cep95_max_m=250.0, pmf_cep95_max_m=250.0),
            required=False,
        ),
        StressCase(
            "adversarial",
            replace(base, use_tercom=False, use_pf=False),
            terrain_fn=adversarial_terrain,
            gates=StressGates(pmf_cep95_max_m=180.0, ekf_cep95_max_m=200.0),
        ),
    ]


def _run_one(args: tuple) -> MonteCarloResult:
    case_name, seed, cfg_dict, terrain_kind = args
    cfg = SimConfig(**cfg_dict)
    terrain_fn = (
        adversarial_terrain if terrain_kind == "adversarial" else Terrain.synthetic
    )
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
        out[f"{f}_rmse"] = float(np.sqrt(np.mean(err**2)))
    ekf_s = _nees_second_half(res.ekf_pos, res.ekf_pcov, res.truth.pos)
    out["ekf_nees"] = float(np.mean(ekf_s))
    out["ekf_nees_s"] = ekf_s
    if res.pmf_err is not None:
        pmf_s = _nees_second_half(res.pmf_pos, res.pmf_pcov, res.truth.pos)
        out["pmf_nees"] = float(np.mean(pmf_s))
        out["pmf_nees_s"] = pmf_s
    if res.pf_err is not None and res.pf_pcov is not None:
        pf_s = _nees_second_half(res.pf_pos, res.pf_pcov, res.truth.pos)
        out["pf_nees"] = float(np.mean(pf_s))
        out["pf_nees_s"] = pf_s
    out["n_ekf_resets"] = int(res.n_ekf_resets)
    out["n_ambiguous"] = int(res.n_ambiguous)
    return out


def _aggregate(rows: list[dict], n_runs: int) -> MonteCarloResult:
    final = {f: [] for f in FILTERS}
    rmse = {f: [] for f in FILTERS}
    nees_all = {"ekf": [], "pf": [], "pmf": []}
    nees_samp = {"ekf": [], "pf": [], "pmf": []}
    resets, ambig = [], []
    for r in rows:
        for f in FILTERS:
            kf, kr = f"{f}_final", f"{f}_rmse"
            if kf in r:
                final[f].append(r[kf])
                rmse[f].append(r[kr])
        for f in ("ekf", "pf", "pmf"):
            if f"{f}_nees" in r:
                nees_all[f].append(r[f"{f}_nees"])
            if f"{f}_nees_s" in r:
                nees_samp[f].append(np.asarray(r[f"{f}_nees_s"]))
        if "n_ekf_resets" in r:
            resets.append(r["n_ekf_resets"])
        if "n_ambiguous" in r:
            ambig.append(r["n_ambiguous"])
    final = {f: np.array(v) for f, v in final.items() if v}
    rmse = {f: np.array(v) for f, v in rmse.items() if v}
    samples = {f: np.concatenate(v) for f, v in nees_samp.items() if v}
    seeds = [r["seed"] for r in rows]
    return MonteCarloResult(
        n_runs=n_runs,
        seeds=seeds,
        final_err=final,
        rmse=rmse,
        ekf_nees=float(np.mean(nees_all["ekf"])) if nees_all["ekf"] else 0.0,
        pmf_nees=float(np.mean(nees_all["pmf"])) if nees_all["pmf"] else 0.0,
        pf_nees=float(np.mean(nees_all["pf"])) if nees_all["pf"] else 0.0,
        nees_samples=samples,
        n_resets=float(np.mean(resets)) if resets else 0.0,
        n_ambiguous=float(np.mean(ambig)) if ambig else 0.0,
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
        if mc.pf_nees > 0.0:
            out["pf_nees"] = gates.pf_nees_min <= mc.pf_nees <= gates.pf_nees_max
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


def run_stress_case(
    case: StressCase, seeds: list[int] | None = None, n_workers: int = 31
) -> StressResult:
    seeds = seeds or list(range(1, 65))
    terrain_kind = "synthetic"
    if case.name == "adversarial":
        terrain_kind = "adversarial"
    elif case.name == "featureless":
        terrain_kind = "featureless"
    cfg_dict = {
        f.name: getattr(case.cfg, f.name)
        for f in case.cfg.__dataclass_fields__.values()
    }
    jobs = [(case.name, s, cfg_dict, terrain_kind) for s in seeds]
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    with Pool(processes=pool_workers(n_workers)) as pool:
        rows = pool.map(_run_one, jobs)
    mc = _aggregate(rows, len(seeds))
    gates = evaluate_gates(mc, case.gates)
    return StressResult(case=case.name, mc=mc, gates=gates, required=case.required)


def run_stress_harness(
    cases: list[StressCase] | None = None,
    seeds: list[int] | None = None,
    n_workers: int = 31,
) -> list[StressResult]:
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
