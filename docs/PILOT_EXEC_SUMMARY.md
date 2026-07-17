# Charybdis Pilot Integration — Executive Summary

**Package:** Charybdis hybrid terrain-aware UUV navigation  
**Preview tag:** `v0.1-integration-preview`  
**Purpose:** Hardware-free evaluation of GPS-denied / submerged navigation aiding

## What it is

Charybdis is a **sensor-fusion and guidance layer**, not a full autonomy stack. Your mission software adapts sensor measurements and logs into `SensorPacket` objects; Charybdis returns navigation state and patrol guidance each cycle. It does **not** command actuators.

```text
your sensors/logs → SensorPacket → HybridNavigator.step() → HybridStepResult
```

## What is supported (stable API)

- Root imports: `HybridNavigator`, `HybridSensorFusion`, `SensorPacket`, `TerrainProfileMatcher`, `PatrolExecutor`
- Construction types: `charybdis.hybrid` measurements, routes, matcher config
- Deterministic **packet replay** for integration testing without hardware
- Versioned artifact schemas (`schema_version == "1"`)

See `docs/STABLE_API.md` for the full contract.

## Evidence included in this kit

| Gate | Result | Notes |
|------|--------|-------|
| CI (`main`) | PASS | Lint, types, architecture, tests |
| Integration grade | PASS | Harbor 7/7 + deep 7/7 @ 64 runs |
| Release grade | PASS | Harbor 7/7 + deep 7/7 @ 256 runs |
| Holdout matrices | PASS | Harbor + deep 7/7 @ 256 runs |
| Mission engineering | PASS | 6/6 @ 256 runs |
| High-res bathymetry | PASS | NOAA P080 @ ~10.3 m, CEP95 **9.78 m**, 256/256 accepted |
| NN SO(2) matcher | Research | Promoted `tcm_so2.pt`; pod retrain improves hard-eval tail |

See [`KNOWN_LIMITS.md`](KNOWN_LIMITS.md) for the current baseline SHA and artifact paths.

## What this is NOT

- Not safety-certified or navigation-grade for real water without your sea trials
- Not a replacement for your mission planner, DVL stack, or vehicle controller
- Not a guarantee on **your** survey bathymetry until validated on your tile

## 15-minute eval (no hardware)

```bash
python -m pip install -c requirements/ci.txt -e ".[dev]"
python examples/verify_pilot_replay.py
```

Expected: deterministic replay PASS against bundled `mission_replay.json`.

## Pilot ask from integrators

To move from replay eval to a 2-week pilot, request:

1. Sample mission log (or synthetic packet stream spec)
2. Survey bounding box for bathymetry characterization
3. Baseline nav error metric (DR/DVL/USBL) for comparison

## Contact framing

> Charybdis passed declared software validation gates for the referenced revision and artifact set. It exposes a stable packet-to-guidance API suitable for integration testing under documented limits.

Do **not** claim field-proven, certified, or fleet-ready without additional evidence.
