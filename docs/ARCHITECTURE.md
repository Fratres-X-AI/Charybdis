# Architecture

## Repository stacks

```
┌──────────────────────────────────────────────────────────┐
│  charybdis/                 installable Python package   │
│    config, terrain, imu, ins, ekf, pf, tercom, ...     │
│    fusion, patrol, sensors, modes   ← hybrid UUV layer   │
│    navigator, simulation, evaluate, stress               │
│    experimental/            NN matcher, SLAM, swarm      │
└──────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────┐
│  console/                   UUV tactical spine (PAUSED)  │
│    charybdis_core, console, sensors, autonomy, ...       │
└──────────────────────────────────────────────────────────┘
```

The GDI library and UUV console share the GPS-denied terrain-aiding problem but
**do not share a single runtime**. Bridge via small APIs (`NavEstimate`, bathymetry
loaders, hybrid `HybridNavState`) — not by merging codebases.

## Package layout

```
charybdis/
  __init__.py          public API (stable / beta)
  fusion.py            hybrid 8D surface/submerged fusion
  patrol.py            waypoint patrol executor
  sensors.py           abstract sensor measurements
  modes.py             surface / submerged mode manager
  navigator.py         TERCOM + EKF + PF coordination
  experimental/        opt-in research (SLAM, swarm, NN)
console/               paused UUV console (separate package)
tests/                 pytest
scripts/               MC, stress, pod helpers
docs/                  MISSION, MATURITY, ARCHITECTURE
run_sim.py             primary simulation entry point
```

## Navigator contract

`Navigator.estimate()` returns `NavEstimate` (position, 2×2 covariance, source
filter, health flags). Downstream layers should consume this — not filter internals.

## Hybrid UUV contract

`HybridSensorFusion.step(SensorPacket)` returns `HybridNavState`. Patrol consumes
`HybridNavState` and emits `PatrolCommand` (desired velocity, heading, depth, mode).

## Import policy

```python
import charybdis                         # stable / beta only
from charybdis.experimental import run_swarm, init_slam
from charybdis.experimental.nn_matcher import train  # needs torch
```

Default `import charybdis` must not load torch or experimental side effects.

Legacy `charybdis.slam` / `charybdis.swarm` / `charybdis.nn_matcher` shims
re-export from `experimental/` with `DeprecationWarning`.
