# Architecture

## Architectural direction

Charybdis has one primary runtime: `charybdis.hybrid`. It supports
surface/submerged UUV navigation research with hardware-neutral measurements,
conservative state estimation, bathymetry-derived position aiding, health
diagnostics, and waypoint guidance.

Three boundaries are intentional:

- `charybdis.legacy` preserves the legacy TERCOM/EKF/PF/PMF terrain-aided stack.
- `charybdis.experimental` contains unstable opt-in research.
- `console/` is paused application source and is not included in the wheel.

The boundaries prevent legacy, experimental, UI, and optional deep-learning
dependencies from entering the default runtime.

## Package boundary

`charybdis/__init__.py` is the curated public surface. It exports exactly the
package version and these hybrid symbols:

```text
BathymetryMap
TerrainProfileMatcher
NavMode
SensorPacket
HybridNavState
HybridSensorFusion
HybridNavigator
HybridStepResult
PatrolExecutor
```

Common construction and packet types are available from `charybdis.hybrid`.
Lower-level diagnostics and implementation helpers require explicit module
imports such as `charybdis.hybrid.fusion` or `charybdis.hybrid.modes`.
Simulation, evaluation, shared data loaders, legacy estimators, and
experimental modules require explicit submodule imports.

The architecture tests enforce that importing `charybdis` does not import
`charybdis.legacy`, `charybdis.experimental`, `console`, or PyTorch.

## Primary hybrid path

The production-facing integration boundary is a sensor cycle, not direct access
to filter internals:

```text
drivers, log replay, or simulation
              |
              v
         SensorPacket
              |
              v
    HybridNavigator.step()
              |
       +------+------+
       |             |
       v             v
HybridNavState   PatrolCommand
```

`HybridNavigator` owns a `HybridSensorFusion` and a `PatrolExecutor`. On every
cycle it fuses the packet first and generates guidance from that exact immutable
state snapshot. `resume()` re-anchors selected state blocks and selects the
nearest route waypoint.

The navigator intentionally does not implement drivers, clock discipline,
mission planning, collision avoidance, vehicle dynamics, low-level control, or
safety interlocks.

## Hybrid components

`charybdis.hybrid.sensors` defines immutable measurement contracts:

- `ImuMeasurement` for horizontal specific force and a positive time step
- `GpsMeasurement` for surface position and optional velocity
- `DepthMeasurement` for positive-down pressure depth
- `VelocityMeasurement` for DVL-style horizontal velocity
- `BathymetryMeasurement` for a position fix or feature range/bearing
- `SensorQuality` for availability and covariance inflation
- `SensorPacket` for one timestamped fusion cycle

`charybdis.hybrid.modes` implements a two-state mode manager. Depth is
authoritative by default. Surface and submerged thresholds form a hysteresis
band, and a route hint cannot override depth outside that band unless an
integrator explicitly changes the configuration.

`charybdis.hybrid.fusion` estimates:

```text
[px, py, depth, vx, vy, depth_rate, bax, bay]
```

Coordinates use a local metric navigation frame; depth is positive down.
Prediction integrates horizontal acceleration, acceleration bias, and a damped
depth-rate model. Measurement covariance is scaled by reported quality.
Linear innovations are chi-square gated, and covariance updates use a
stabilized Joseph form.

GPS is processed only in surface mode. Bathymetry fixes are processed only in
submerged mode. Depth and velocity measurements can be processed in either
mode. Rejections are bounded in history and contribute to `FusionDiagnostics`.
Diagnostics expose recent accepted aiding sources. Position uncertainty,
covariance validity, and recent rejection count determine filter health.

`charybdis.hybrid.bathymetry` provides deterministic profile matching:

```text
BathymetryProfile + prior state + BathymetryMap
                         |
                         v
                TerrainProfileMatcher
                         |
                         v
     accepted BathymetryMeasurement or a rejection status
```

The matcher searches a regular local grid, rejects insufficient relief,
out-of-bounds searches, high residuals, and ambiguous minima, and derives a
position covariance from nearby candidates. Matching is not performed
automatically by `HybridNavigator`; the integration layer decides when to run
the matcher and places only an accepted measurement into the next packet.

`charybdis.hybrid.patrol` performs heading-aware line-of-sight waypoint
guidance. A `PatrolCommand` contains desired horizontal velocity and heading,
target depth and mode, waypoint index, and route-completion state. Guidance
commands zero horizontal velocity when filter health is false or the configured
navigation-error limit is exceeded. This is a conservative hold, not a complete
vehicle fail-safe.

## Shared simulation and evaluation

Shared modules remain outside the root API:

- `charybdis.simulation` exposes deterministic hybrid and legacy simulations.
- `charybdis.evaluation` exposes Monte Carlo summaries, stress tools, and
  validation artifact helpers.
- `charybdis.bathy` loads or converts external bathymetry into package models.
- `charybdis.config`, `terrain`, `trajectory`, `imu`, and `ins` support the
  retained legacy TAN simulations.

Explicit imports keep application dependencies and research workflows visible:

```python
from charybdis.evaluation import run_hybrid_montecarlo
from charybdis.simulation import HybridHarborConfig
```

## Legacy and experimental stacks

The legacy stack has its own estimator state and sensor assumptions. Use it only
for legacy terrain-aided simulation, regression work, or maintained consumers:

```python
from charybdis.config import SimConfig
from charybdis.legacy import NavEstimate, Navigator
```

Legacy `Navigator.estimate()` returns a `NavEstimate` contract instead of a
hybrid state. There is no supported conversion between the two estimator
states.

Experimental imports are always explicit:

```python
from charybdis.experimental import init_slam, run_swarm
from charybdis.experimental.nn_matcher import train
```

Experimental APIs may change and may require optional dependencies. Root-level
legacy and experimental compatibility modules are intentionally absent.

## Packaging and console

The Hatch wheel target packages only `charybdis`. The repository-level
`console/` tree is therefore not installed with the wheel; CI inspects the wheel
to enforce that exclusion. Installing the optional `console` dependencies does
not install or activate the paused console source.

Validation scope, provenance, metrics, and limitations are documented in
[`VALIDATION.md`](VALIDATION.md).
