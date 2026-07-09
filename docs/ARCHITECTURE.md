# Architecture

## Current status

- **Primary development:** `charybdis.hybrid` for harbor UUV surface/submerged
  navigation and patrol execution.
- **Maintained legacy:** `charybdis.legacy` for interceptor TERCOM/EKF/PF/PMF
  simulations and compatibility.
- **Experimental:** `charybdis.experimental` for opt-in, unstable research.
- **Paused:** `console/` is isolated from the navigation package.

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

## Hybrid vs Legacy Navigation

| Question | `charybdis.hybrid` | `charybdis.legacy` |
|---|---|---|
| Primary use case | Harbor UUV patrol above and below the surface | Original interceptor terrain-aided navigation |
| State model | 8D horizontal, vertical, and bias state | 6D horizontal position, velocity, and bias state |
| Sensor inputs | GPS, IMU, depth, DVL-style velocity, bathymetry | IMU, radar/barometer terrain observations, TERCOM |
| Estimators | Conservative EKF-style hybrid fusion | EKF, particle filter, point-mass filter, TERCOM |
| Maintenance status | Active and recommended for new work | Maintained for reference and compatibility |
| Import path | `from charybdis.hybrid import ...` | `from charybdis.legacy import ...` |

Use `charybdis.hybrid` for all new harbor UUV navigation, mode-transition, and
patrol work. Use `charybdis.legacy` only when reproducing interceptor
simulations, evaluating TERCOM/TRN filters, or maintaining existing consumers.
The two stacks share terrain, configuration, IMU, simulation, and evaluation
infrastructure but do not share estimator state.

### Hybrid 8D state

`HybridSensorFusion` estimates:

| Indices | State | Meaning |
|---|---|---|
| 0–1 | `px`, `py` | Horizontal position in the local navigation frame |
| 2 | `depth` | Positive-down depth |
| 3–4 | `vx`, `vy` | Horizontal velocity |
| 5 | `depth_rate` | Positive-down vertical speed |
| 6–7 | `bax`, `bay` | Horizontal accelerometer bias |

The complete state is:

```text
[px, py, depth, vx, vy, depth_rate, bax, bay]
```

Prediction integrates horizontal acceleration and a damped constant-rate depth
model. Measurement updates use quality-scaled covariance and chi-square gates.
GPS is accepted while surfaced; bathymetry fixes are accepted while submerged.

## Navigator contract

`Navigator.estimate()` returns `NavEstimate` (position, 2×2 covariance, source
filter, health flags). Downstream layers should consume this — not filter internals.

## Hybrid UUV contract

`HybridSensorFusion.step(SensorPacket)` returns `HybridNavState`. Patrol consumes
`HybridNavState` and emits `PatrolCommand` (desired velocity, heading, depth, mode).

The fusion layer owns state estimation and sensor acceptance. The patrol layer
only consumes navigation state and emits guidance commands; it does not inspect
filter internals.

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
