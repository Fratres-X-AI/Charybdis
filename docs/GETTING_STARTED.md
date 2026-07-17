# Getting Started

This guide shows the stable hybrid navigation path. It does not use simulation,
legacy estimators, experimental modules, or the paused console.

## Install

Use Python 3.11 or newer:

```bash
python -m pip install -e .
```

For development checks:

```bash
python -m pip install -e ".[dev]"
```

## Stable Imports

The root package is intentionally small:

```python
from charybdis import HybridNavigator, HybridSensorFusion, PatrolExecutor, SensorPacket
from charybdis import NavMode
from charybdis.hybrid import DepthMeasurement, GpsMeasurement, ImuMeasurement
from charybdis.hybrid import PatrolRoute, Waypoint
```

Use explicit module imports for lower-level diagnostics or research helpers.

## Build A Navigator

Create a route, fusion filter, patrol executor, and navigator:

```python
route = PatrolRoute(
    (
        Waypoint([20.0, 0.0], mode=NavMode.SURFACE, radius_m=3.0),
        Waypoint([60.0, 0.0], mode=NavMode.SUBMERGED, depth_m=8.0, radius_m=5.0),
    )
)
fusion = HybridSensorFusion(pos0=[0.0, 0.0])
patrol = PatrolExecutor(route)
navigator = HybridNavigator(fusion, patrol)
```

`HybridNavigator.step()` is the main integration point. It fuses one coherent
packet, then generates guidance from the resulting immutable state.

## Send One Sensor Packet

Use one timestamp for the packet and any measurements in that packet:

```python
packet = SensorPacket(
    imu=ImuMeasurement([0.0, 0.0], dt=1.0, timestamp_s=1.0),
    gps=GpsMeasurement([0.5, 0.0], timestamp_s=1.0),
    depth=DepthMeasurement(0.0, timestamp_s=1.0),
    timestamp_s=1.0,
)
result = navigator.step(packet)
```

The result contains:

- `result.state`: position, velocity, covariance, mode, health, and diagnostics.
- `result.command`: desired horizontal velocity, target depth, and waypoint state.

## Interpret Health

`result.state.filter_healthy` is the estimator health decision. `PatrolExecutor`
holds horizontal velocity at zero when navigation is unhealthy or uncertainty
exceeds its configured limit.

This is a guidance behavior, not a safety system. Vehicle integrations still
need independent supervision, emergency handling, collision avoidance, and
control allocation.

## Terrain Aiding

Use `BathymetryMap`, `BathymetryProfile`, and `TerrainProfileMatcher` to create
a quality-gated `BathymetryMeasurement`. Fuse only accepted terrain matches.
See `[examples/terrain_profile_matching.py](../examples/terrain_profile_matching.py)`.

## Next Steps

- Run `[examples/adapter_pattern.py](../examples/adapter_pattern.py)` for the
  recommended adapter → navigator → command handoff structure.
- Read `[docs/PRODUCTION_INTEGRATION.md](PRODUCTION_INTEGRATION.md)` before
  connecting real logs or hardware.
- Read `[docs/VALIDATION.md](VALIDATION.md)` for CI, RunPod Phase 2, and
  validation commands.
- Read `[docs/RUNPOD.md](RUNPOD.md)` for GPU pod training and the green gate.

