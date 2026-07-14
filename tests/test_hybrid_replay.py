"""Deterministic packet-log replay regression tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from charybdis.evaluation.packet_replay import (
    REPLAY_SCHEMA_VERSION,
    ReplayManifest,
    assert_replay_matches,
    load_replay_log,
    record_harbor_packets,
    replay_packets,
    save_replay_log,
)
from charybdis.simulation.hybrid import HybridHarborConfig


def test_harbor_packet_replay_is_bitwise_deterministic(tmp_path: Path) -> None:
    cfg = HybridHarborConfig(seed=11, max_steps=80)
    log = record_harbor_packets(cfg, max_steps=80)
    first = replay_packets(log)
    second = replay_packets(log)
    assert_replay_matches(first, second)

    target = tmp_path / "harbor_replay.json"
    save_replay_log(target, log)
    loaded = replay_packets(load_replay_log(target))
    assert_replay_matches(first, loaded)


def test_harbor_packet_roundtrip_preserves_packet_count() -> None:
    log = record_harbor_packets(HybridHarborConfig(seed=3), max_steps=40)
    assert len(log.packets) == 40


def test_replay_manifest_schema_version_is_explicit() -> None:
    log = record_harbor_packets(HybridHarborConfig(seed=5), max_steps=4)

    assert log.manifest.schema_version == REPLAY_SCHEMA_VERSION


def test_replay_manifest_rejects_unknown_schema_version() -> None:
    log = record_harbor_packets(HybridHarborConfig(seed=7), max_steps=4)
    payload = log.manifest.to_dict()
    payload["schema_version"] = "999"

    with pytest.raises(ValueError, match="unsupported replay schema version"):
        ReplayManifest.from_dict(payload)
