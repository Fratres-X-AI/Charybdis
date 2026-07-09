# Architecture

## Repository stacks

```
┌──────────────────────────────────────────────────────────┐
│  charybdis/                 installable Python package   │
│    config, terrain, imu, ins, bathy                      │
│    hybrid/          surface/submerged UUV (primary)      │
│    legacy/          interceptor TERCOM/EKF/PF/PMF        │
│    simulation/      sim harnesses                        │
│    evaluation/      Monte-Carlo + stress gates           │
│    experimental/    SLAM, swarm, NN matcher (opt-in)     │
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
  __init__.py          curated public API
  config.py, terrain.py, trajectory.py, imu.py, ins.py, bathy.py
  hybrid/              fusion, patrol, sensors, modes (primary UUV)
  legacy/              navigator, ekf, pf, pmf, tercom (interceptor)
  simulation/          simulation harnesses
  evaluation/          Monte-Carlo and stress gates
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
import charybdis                         # curated stable / beta API
from charybdis.hybrid import HybridSensorFusion, PatrolExecutor
from charybdis.legacy import Navigator, NavEstimate
from charybdis.experimental import run_swarm, init_slam
from charybdis.experimental.nn_matcher import train  # needs torch
from charybdis.evaluation import run_stress_harness
from charybdis.bathy import load_npz              # advanced submodule
```

Default `import charybdis` must not load torch or experimental side effects.
Root-level experimental shims (`charybdis.slam`, `charybdis.swarm`,
`charybdis.nn_matcher`) have been removed — use `charybdis.experimental.*`.
