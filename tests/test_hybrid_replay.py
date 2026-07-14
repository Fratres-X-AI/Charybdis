"""Deterministic packet-log replay regression tests."""

from __future__ import annotations

from pathlib import Path

from charybdis.evaluation.packet_replay import (
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
