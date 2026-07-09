# Examples

Install the package from the repository root before running an example:

```bash
python -m pip install -e .
```

All examples are deterministic, use public APIs, and run without external data
or hardware.

## HybridNavigator production wiring

```bash
python examples/run_hybrid_patrol.py
```

`run_hybrid_patrol.py` builds a `HybridSensorFusion`, `PatrolExecutor`, and
`HybridNavigator`, then places the navigator between a sensor adapter and a
command consumer. The simulated adapter emits coherent timestamps, surface GPS,
submerged velocity, depth, and IMU measurements. A real integration would
replace that adapter and send `PatrolCommand` through an independently
supervised vehicle controller.

The example demonstrates integration boundaries; it is not deployable vehicle
control software.

## Adapter pattern

```bash
python examples/adapter_pattern.py
```

`adapter_pattern.py` separates four responsibilities that should stay separate
in production code: sensor packet assembly, `HybridNavigator.step()`, health
policy, and command handoff to a supervised controller boundary.

## Terrain profile matching

```bash
python examples/terrain_profile_matching.py
```

`terrain_profile_matching.py` samples a positive-down synthetic bathymetry map,
searches around an uncertain position prior, checks the match status, and puts
only an accepted `BathymetryMeasurement` into a submerged fusion packet. Map
coordinates, profile offsets, and depth values must share a frame and vertical
datum in a real integration.

## Degraded sensors

```bash
python examples/degraded_sensors.py
```

`degraded_sensors.py` distinguishes a sensor explicitly marked unavailable from
an available but statistically inconsistent measurement. It shows covariance
growth during GPS dropout, innovation rejection for a GPS outlier, health
degradation under a strict example policy, and the patrol layer's zero-velocity
hold.

The hold is a library behavior, not a complete safety or emergency system.

## Explicit legacy usage

```bash
python examples/legacy_interceptor.py
```

`legacy_interceptor.py` imports `Navigator` from `charybdis.legacy`, constructs
the shared interceptor configuration and terrain explicitly, and runs one
EKF/TRN cycle. This import path is retained for legacy simulation and
comparison. New surface/submerged UUV work should use the hybrid API.

## Relationship to Phase 2

The examples are deterministic integration demonstrations and CI smoke checks;
they are not Monte Carlo or release evidence. In particular,
`terrain_profile_matching.py` uses a small synthetic map. The separate Phase 2
workflow runs seven synthetic scenarios at 64 and 256 seeds per scenario and
characterizes the matcher against a provenance-tracked projected GEBCO tile.

Even that GEBCO phase synthesizes vehicle positions, profiles, prior errors, and
measurement noise. It does not turn this example or the package into
navigation-certified or sea-trial-validated software. See
[`../docs/VALIDATION.md`](../docs/VALIDATION.md) for exact commands, confidence
gates, artifacts, and limitations.

## Development checks

```bash
ruff check examples
ruff format --check examples
```

CI also executes every `examples/*.py` file on Python 3.12 after the editable
install.
