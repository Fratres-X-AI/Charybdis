import json

from charybdis.evaluation import (
    ValidationManifest,
    load_validation_seeds,
    run_hybrid_montecarlo,
    write_validation_artifact,
)
from charybdis.simulation import HybridHarborConfig


def test_hybrid_montecarlo_is_deterministic_and_serial_in_pytest():
    seeds = (11, 22)

    first = run_hybrid_montecarlo(
        HybridHarborConfig(),
        seeds=seeds,
        workers=31,
    )
    second = run_hybrid_montecarlo(HybridHarborConfig(), seeds=seeds)

    assert first.to_dict() == second.to_dict()
    assert first.route_completion_rate == 1.0
    assert first.cep95_m < 10.0


def test_validation_manifest_roundtrip(tmp_path):
    seed_path = tmp_path / "seeds.txt"
    seed_path.write_text("# fixed\n11\n22\n", encoding="utf-8")
    seeds = load_validation_seeds(seed_path)
    manifest = ValidationManifest(
        git_sha="abc123",
        seeds=seeds,
        workers=1,
        scenario="test",
        config={"fault": None},
    )

    destination = write_validation_artifact(
        tmp_path / "artifact.json",
        manifest=manifest,
        results={"cep95_m": 1.25},
    )
    payload = json.loads(destination.read_text(encoding="utf-8"))

    assert payload["manifest"]["seeds"] == [11, 22]
    assert payload["results"]["cep95_m"] == 1.25
