#!/usr/bin/env python3
"""Run confidence-bounded hybrid validation across the release scenario matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import time
from dataclasses import asdict
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np
from charybdis.evaluation import (
    VALIDATION_ARTIFACT_SCHEMA_VERSION,
    VALIDATION_SCENARIOS,
    ValidationManifest,
    assess_validation,
    build_validation_scenario,
    load_validation_seeds,
    run_hybrid_montecarlo,
    validation_gates,
    write_validation_artifact,
)
from charybdis.simulation import build_synthetic_harbor_map


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        text=True,
        encoding="utf-8",
    ).strip()


def _peak_rss_mib() -> float | None:
    try:
        import resource
    except ImportError:
        return None
    own = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    children = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    scale = 1024.0 if platform.system() != "Darwin" else 1024.0**2
    return float(max(own, children) / scale)


def _json_ready(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_report(
    path: Path,
    *,
    tier: str,
    runs: int,
    git_sha: str,
    scenarios: dict[str, dict[str, Any]],
) -> None:
    lines = [
        "# Hybrid validation report",
        "",
        f"- Tier: `{tier}`",
        f"- Runs per scenario: `{runs}`",
        f"- Git SHA: `{git_sha}`",
        f"- Generated: `{datetime.now(UTC).isoformat()}`",
        "",
        "## Scenario outcomes",
        "",
    ]
    for name, payload in scenarios.items():
        result = payload["results"]
        assessment = payload["assessment"]
        lines.extend(
            [
                f"### {name}",
                "",
                f"- Gate result: **{'PASS' if assessment['passed'] else 'FAIL'}**",
                f"- CEP95: `{result['cep95_m']:.3f} m`",
                f"- Depth CEP95: `{result['depth_cep95_m']:.3f} m`",
                f"- Route completion: `{result['route_completion_rate']:.3%}`",
                f"- Healthy final state: `{result['healthy_rate']:.3%}`",
                f"- Divergence (>50 m): `{result['divergence_rate_50m']:.3%}`",
                f"- GPS reacquisition jump CEP95: `{result['gps_reacquisition_jump_cep95_m']:.3f} m`",
                f"- Runtime: `{result['runtime_s']:.3f} s`",
                "",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    """Run the selected engineering or release matrix."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", choices=("engineering", "release"), required=True)
    parser.add_argument("--runs", type=int)
    parser.add_argument("--workers", type=int, default=31)
    parser.add_argument("--seeds", default="validation/seeds_v1.txt")
    parser.add_argument("--output-dir")
    parser.add_argument(
        "--scenarios",
        nargs="+",
        choices=VALIDATION_SCENARIOS,
        default=list(VALIDATION_SCENARIOS),
    )
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()

    runs = args.runs or (64 if args.tier == "engineering" else 256)
    if not 2 <= runs <= 512:
        parser.error("--runs must be between 2 and 512")
    if not 1 <= args.workers <= 31:
        parser.error("--workers must be between 1 and 31")
    dirty = bool(_git("status", "--porcelain"))
    if dirty and not args.allow_dirty:
        parser.error("validation requires a clean git worktree")

    git_sha = _git("rev-parse", "HEAD")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path(
        args.output_dir or f"artifacts/validation/{stamp}-{git_sha[:12]}/{args.tier}"
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    seeds = load_validation_seeds(args.seeds, limit=runs)
    harbor_map = build_synthetic_harbor_map()
    map_sha256 = hashlib.sha256(harbor_map.depth_grid_m.tobytes()).hexdigest()
    scenario_payloads: dict[str, dict[str, Any]] = {}

    for name in args.scenarios:
        config = build_validation_scenario(name)
        start = time.perf_counter()
        result = run_hybrid_montecarlo(
            config,
            seeds=seeds,
            workers=args.workers,
        )
        elapsed = time.perf_counter() - start
        gates = validation_gates(name)
        assessment = assess_validation(result, gates)
        metrics = result.to_dict()
        metrics.update(
            {
                "runtime_s": elapsed,
                "peak_rss_mib": _peak_rss_mib(),
            }
        )
        manifest = ValidationManifest(
            git_sha=git_sha,
            seeds=seeds,
            workers=args.workers,
            scenario=name,
            config={
                "tier": args.tier,
                "dirty_worktree": dirty,
                "seed_file": str(Path(args.seeds)),
                "synthetic_map_sha256": map_sha256,
                "scenario": _json_ready(asdict(config)),
            },
        )
        artifact = output_dir / f"{name}.json"
        write_validation_artifact(
            artifact,
            manifest=manifest,
            results={
                **metrics,
                "gates": _json_ready(asdict(gates)),
                "assessment": assessment.to_dict(),
            },
        )
        scenario_payloads[name] = {
            "artifact": artifact.name,
            "results": metrics,
            "assessment": assessment.to_dict(),
        }
        print(
            f"{name}: {'PASS' if assessment.passed else 'FAIL'} "
            f"cep95={result.cep95_m:.3f}m runtime={elapsed:.2f}s",
            flush=True,
        )

    passed = all(
        payload["assessment"]["passed"] for payload in scenario_payloads.values()
    )
    summary = {
        "schema_version": VALIDATION_ARTIFACT_SCHEMA_VERSION,
        "tier": args.tier,
        "runs_per_scenario": runs,
        "workers": args.workers,
        "git_sha": git_sha,
        "dirty_worktree": dirty,
        "passed": passed,
        "scenarios": scenario_payloads,
    }
    _write_json(output_dir / "matrix_summary.json", summary)
    _write_report(
        output_dir / "REPORT.md",
        tier=args.tier,
        runs=runs,
        git_sha=git_sha,
        scenarios=scenario_payloads,
    )
    print(output_dir, flush=True)
    return 0 if args.tier == "engineering" or passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
