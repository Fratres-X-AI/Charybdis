# Production Integration Guide

Charybdis provides navigation estimates and patrol guidance for research-grade
surface/submerged UUV workflows. It is not a certified autonomy stack, safety
controller, or actuator controller.

## Stable Runtime Boundary

The production-facing loop is:

```text
sensor adapters -> SensorPacket -> HybridNavigator.step() -> PatrolCommand
```

Adapters own hardware, clocks, calibration, logging, and unit conversion.
`HybridNavigator` owns the order of operations: fuse first, then produce
guidance from the exact returned `HybridNavState`.

## Required Integrator Responsibilities

Before using real logs or hardware, define and test:

- Local navigation frame, axis convention, and map origin.
- Positive-down depth convention and vertical datum.
- Timestamp source, monotonicity policy, and packet assembly latency.
- Sensor covariance models, outage reporting, and quality scaling.
- Independent safety interlocks and emergency behaviors.
- Control allocation and actuator saturation handling.
- Mission supervision, collision avoidance, geofencing, and operator override.
- Map provenance, resolution limits, and non-navigation warnings for public data.

The library does not infer these policies.

## Sensor Packet Policy

Each `SensorPacket` should represent one coherent fusion cycle. If individual
measurements carry timestamps, the packet must carry a timestamp too, and no
measurement timestamp may be later than the packet timestamp.

Unavailable sensors should be represented with `SensorQuality(available=False)`
rather than fake high-confidence values. Available but inconsistent measurements
are innovation-gated and may count toward health diagnostics.

## Mode And Aiding Rules

Depth is authoritative by default. GPS is fused only in surface mode. Bathymetry
position fixes are fused only in submerged mode. Velocity and depth updates can
be used in either mode.

Route hints should not be treated as truth. They are useful for command intent,
but integrations should keep depth thresholds, sensor availability, and safety
policies independent.

## Health And Command Handoff

`HybridNavState.filter_healthy` summarizes covariance validity, uncertainty, and
recent rejections. `PatrolExecutor` can hold guidance when the state is unhealthy
or position uncertainty is too large.

Treat `PatrolCommand` as guidance. A vehicle controller must still enforce
limits, failsafes, obstacle avoidance, and operator authority before actuating.

## Optional And Research Code

`charybdis.legacy`, `charybdis.experimental`, `charybdis.simulation`, and
`charybdis.evaluation` are explicit opt-in surfaces. They do not load from
`import charybdis` and should not be used as production integration APIs.

The repository-level `console/`, `ros2_ws/`, `scripts/`, and examples are not
shipped in the wheel. They are demos, validation tools, or paused application
source.

## Validation Expectations

Run local CI gates before integration changes. Run RunPod Phase 1 for package
acceptance and Phase 2 when fusion, matcher, scenario, or validation behavior
changes. See `[docs/VALIDATION.md](VALIDATION.md)` for exact commands and
limitations.

