# Stable API

Charybdis exposes a deliberately small integration API. Anything outside this
document is available for development and validation, but is not a stable
runtime contract unless it is later promoted here.

## Supported Runtime Imports

The package root is the primary runtime surface:

```python
from charybdis import (
    BathymetryMap,
    HybridNavState,
    HybridNavigator,
    HybridSensorFusion,
    HybridStepResult,
    NavMode,
    PatrolExecutor,
    SensorPacket,
    TerrainProfileMatcher,
    __version__,
)
```

`charybdis.hybrid` is the supported construction surface for measurement,
configuration, route, and matcher types:

```python
from charybdis.hybrid import (
    BathymetryMeasurement,
    BathymetryProfile,
    DepthMeasurement,
    GpsMeasurement,
    HybridFusionConfig,
    ImuMeasurement,
    MatchStatus,
    PatrolCommand,
    PatrolRoute,
    SensorQuality,
    TerrainMatcherConfig,
    VelocityMeasurement,
    Waypoint,
)
```

## Runtime Boundary

The stable runtime loop is:

```text
sensor/log adapters -> SensorPacket -> HybridNavigator.step() -> HybridStepResult
```

`HybridStepResult.state` is the navigation estimate for that fusion cycle.
`HybridStepResult.command` is guidance for an external controller. Charybdis does
not command actuators.

## Explicit Non-Stable Surfaces

These modules are opt-in and not part of the stable runtime API:

- `charybdis.evaluation`
- `charybdis.simulation`
- `charybdis.legacy`
- `charybdis.experimental`
- repository-level `scripts/`, `console/`, `ros2_ws/`, and examples

They may change as validation and research work evolves.

## Artifact Schema Versions

Integration-facing artifact versions are named constants:

- replay logs: `charybdis.evaluation.REPLAY_SCHEMA_VERSION == "1"`
- validation artifacts: `charybdis.evaluation.VALIDATION_ARTIFACT_SCHEMA_VERSION == "1"`
- real-bathymetry validation: `scripts.real_bathymetry_validate.REAL_BATHYMETRY_SCHEMA_VERSION == "1"`

Unknown replay schema versions are rejected at load time. Validation and
real-bathymetry outputs carry top-level `schema_version` fields so archived
artifacts can be interpreted without source-code archaeology.

## Compatibility Policy

Patch releases must preserve the imports and field meanings listed here. If a
future change needs to break one of these contracts, it must either:

1. increment the relevant schema version, or
2. introduce a new stable symbol while keeping the previous one available for a
   documented migration window.

