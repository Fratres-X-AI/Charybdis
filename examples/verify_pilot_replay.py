#!/usr/bin/env python3
"""Verify bundled pilot replay log is deterministic (hardware-free integration check)."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from charybdis.evaluation import (
    REPLAY_SCHEMA_VERSION,
    assert_replay_matches,
    load_replay_log,
    replay_packets,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replay",
        default="pilot_integration_kit/samples/mission_replay.json",
    )
    parser.add_argument(
        "--meta",
        default="",
        help="optional mission_replay.meta.json for sha256 check",
    )
    args = parser.parse_args()

    replay_path = Path(args.replay)
    if not replay_path.exists():
        print(f"MISSING replay file: {replay_path}", file=sys.stderr)
        return 1

    meta_path = Path(args.meta) if args.meta else replay_path.with_suffix(".meta.json")
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(replay_path.read_bytes()).hexdigest()
        if digest != meta.get("sha256"):
            print("FAIL sha256 mismatch", file=sys.stderr)
            return 1

    log = load_replay_log(replay_path)
    if log.manifest.schema_version != REPLAY_SCHEMA_VERSION:
        print(f"FAIL schema {log.manifest.schema_version!r}", file=sys.stderr)
        return 1

    first = replay_packets(log)
    second = replay_packets(log)
    assert_replay_matches(first, second)

    print(
        f"PILOT_REPLAY_VERIFY_PASS steps={len(first)} "
        f"schema={REPLAY_SCHEMA_VERSION} final_pos={first[-1].state.pos.tolist()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
