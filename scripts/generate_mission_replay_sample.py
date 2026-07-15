#!/usr/bin/env python3
"""Generate the pilot integration kit sample replay log."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from charybdis.evaluation import (
    REPLAY_SCHEMA_VERSION,
    assert_replay_matches,
    load_replay_log,
    record_harbor_packets,
    replay_packets,
    save_replay_log,
)
from charybdis.simulation.hybrid import HybridHarborConfig


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            encoding="utf-8",
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="pilot_integration_kit/samples/mission_replay.json",
    )
    parser.add_argument("--steps", type=int, default=120)
    parser.add_argument("--seed", type=int, default=23390824)
    args = parser.parse_args()

    cfg = HybridHarborConfig(seed=args.seed)
    log = record_harbor_packets(cfg, max_steps=args.steps)
    if log.manifest.schema_version != REPLAY_SCHEMA_VERSION:
        raise SystemExit("replay schema mismatch")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    save_replay_log(output, log)

    reference = replay_packets(log)
    reloaded = load_replay_log(output)
    replayed = replay_packets(reloaded)
    assert_replay_matches(reference, replayed)

    payload = output.read_bytes()
    metadata = {
        "file": output.name,
        "schema_version": REPLAY_SCHEMA_VERSION,
        "git_sha": _git_sha(),
        "steps": args.steps,
        "seed": args.seed,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "final_position_m": list(reference[-1].state.pos),
        "final_mode": reference[-1].state.mode.value,
        "waypoint_index": reference[-1].command.waypoint_index,
        "replay_deterministic": True,
    }
    output.with_suffix(".meta.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
