# Pilot Integration Kit

This kit packages everything an AUV integrator needs for a **2-week technical
evaluation** without access to the full development repository or RunPod hosts.

## Contents

After running `scripts/build_pilot_integration_kit.sh`, the zip contains:

| Path | Description |
|------|-------------|
| `wheel/charybdis-*.whl` | Built package for the tagged revision |
| `requirements-ci.txt` | Pinned CI constraints for reproducible install |
| `docs/STABLE_API.md` | Supported runtime contract |
| `docs/PILOT_EXEC_SUMMARY.md` | One-page executive summary |
| `docs/INTEGRATION_HANDOFF.md` | Full handoff bundle specification |
| `docs/KNOWN_LIMITS.md` | Explicit non-claims and scope limits |
| `samples/mission_replay.json` | Deterministic harbor replay sample |
| `samples/mission_replay.meta.json` | SHA-256 and replay metadata |
| `examples/verify_pilot_replay.py` | 15-minute hardware-free check |
| `evidence/integration_grade/` | Harbor + deep engineering summaries |
| `evidence/release_grade/` | Harbor + deep release summaries |
| `evidence/highres_bathymetry/` | NOAA high-res matcher PASS artifacts |
| `evidence/CI.txt` | Green CI run URL for the source revision |
| `MANIFEST.json` | Kit manifest with git SHA and file inventory |

Large binary tiles (`.npz`, `.nc`) are **not** bundled by default. Request them
separately if needed for bathymetry replay on your region.

## Build the kit

From a clean checkout at the preview tag:

```bash
bash scripts/build_pilot_integration_kit.sh
```

Output:

```text
dist/charybdis_pilot_integration_kit_v0.1-integration-preview.zip
```

## Install from the kit

```bash
python -m pip install --upgrade pip
python -m pip install -c requirements-ci.txt wheel/charybdis-*.whl
python -m pip install -c requirements-ci.txt pytest  # optional, for verify script
```

Or editable from source (if you have the full repo):

```bash
python -m pip install -c requirements/ci.txt -e ".[dev]"
```

## Verify (15 minutes)

```bash
python examples/verify_pilot_replay.py \
  --replay samples/mission_replay.json
```

Expected output ends with `PILOT_REPLAY_VERIFY_PASS`.

## Replay API check

```python
from charybdis.evaluation import (
    REPLAY_SCHEMA_VERSION,
    load_replay_log,
    replay_packets,
)

log = load_replay_log("samples/mission_replay.json")
assert log.manifest.schema_version == REPLAY_SCHEMA_VERSION
results = replay_packets(log)
print(len(results), results[-1].state.pos)
```

## Evidence revision

This kit is pinned to:

- **Git tag:** `v0.1-integration-preview`
- **Baseline SHA:** `cc4321b` (CI green)
- **CI run:** https://github.com/Fratres-X-AI/Charybdis/actions/runs/29365217553

Reproduce full validation on a prepared host using `docs/INTEGRATION_HANDOFF.md`.

## Next step: operator pilot

1. Provide sample logs or a `SensorPacket` adapter sketch.
2. Provide survey bbox for a customer bathymetry tile.
3. Run 2-week eval: replay → region bathy → error comparison vs your baseline.

See `docs/PILOT_EXEC_SUMMARY.md` for the operator-facing summary.
