# Feature maturity

Maturity labels describe API support and simulation evidence. They do not imply
vehicle qualification, safety assurance, hardware compatibility, or
certification.

## Labels

- **Stable research API** — part of the supported package boundary, covered by
  regression tests, and changed with compatibility in mind.
- **Beta** — exercised and useful, but configuration, behavior, or interfaces
  may change as validation expands.
- **Maintained legacy** — retained for compatibility and comparative research;
  fixes are accepted, but it is not the default design path.
- **Experimental** — opt-in research that may be incomplete, computationally
  expensive, or incorrect outside its test scenarios.
- **Paused** — source is retained, but active product work and release support
  are not promised.
- **Operational tooling** — scripts for development infrastructure, not a
  library API.

## Stable research API

The root `charybdis` interface is hybrid-only and considered the supported
research API:

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

The supporting measurement contracts, immutable state snapshots, mode
hysteresis, covariance and innovation checks, deterministic navigator ordering,
and navigation-health hold behavior are covered by fast tests.

Stable here means that consumers should use these contracts instead of
implementation internals. It does not mean the estimator has been validated
with a physical vehicle or approved for operational control.

## Beta hybrid capabilities

The following are active but should be treated as beta:

- detailed tuning objects such as `HybridFusionConfig`,
  `ModeManagerConfig`, and `TerrainMatcherConfig`
- bathymetry-profile search thresholds and covariance heuristics
- heading-aware waypoint guidance tuning and resume policy
- synthetic harbor simulation in `charybdis.simulation.hybrid`
- hybrid Monte Carlo aggregation, named scenario matrices, confidence
  assessment, and JSON validation artifacts
- external bathymetry conversion in `charybdis.bathy`
- GEBCO download/projection and real-map matcher characterization tooling

These paths have unit and deterministic simulation coverage. Their default
parameters are research defaults, not field-calibrated values.

## Maintained legacy

`charybdis.legacy` contains the interceptor `Navigator`, `NavEstimate`, TERCOM,
EKF, particle filter, and point-mass filter. Shared interceptor support modules
include `config`, `terrain`, `trajectory`, `imu`, `ins`, `action_envelope`,
`pcrb`, and associated simulation/evaluation code.

Legacy code remains available for regression, comparison, and existing internal
consumers. It requires explicit imports, is not exported from `charybdis`, and
must not become a dependency of `charybdis.hybrid`.

## Experimental

The following remain opt-in:

- `charybdis.experimental.nn_matcher`
- `charybdis.experimental.slam`
- `charybdis.experimental.swarm`

They are not loaded by `import charybdis`. The neural matcher requires the
optional `nn` dependency group. Experimental results should not be presented as
hybrid-stack validation unless the experiment, baseline, seeds, configuration,
and artifact provenance are reported separately.

## Paused console

The repository-level `console/` source is paused and outside the installable
package. It is excluded from built wheels. Its Streamlit UI and related source
do not define the current navigation API, and installing the `console`
dependency group does not alter this packaging boundary.

## Current evidence

Fast CI currently provides:

- lint and formatting checks
- static typing for the primary hybrid, bathymetry, simulation, and validation
  paths
- Python 3.11 and 3.12 tests
- architecture-boundary checks
- package and hybrid coverage thresholds
- wheel-content and clean-install smoke tests

RunPod Phase 2 provides seven fixed-seed synthetic scenarios at 64-run
engineering and 256-run release tiers. It applies internal release gates to 95%
Wilson or deterministic bootstrap interval endpoints, records full scenario
configuration and map/source hashes, characterizes the matcher on a projected
GEBCO tile, captures dependencies, and inventories completed artifacts.

The release tier is blocking for the checks that are implemented. The declared
GPS-reacquisition-jump threshold is not yet computed or assessed. The GEBCO
phase uses a real map but synthetic positions and observations.

This evidence does not provide hardware-in-the-loop results, field or sea-trial
data, an independent implementation, operational acceptance, or certification.
See [`VALIDATION.md`](VALIDATION.md).

## Promotion requirements

Beta behavior should move into the stable research API only when:

1. its contract and failure behavior are explicit;
2. covariance or another uncertainty measure is exposed where applicable;
3. deterministic regression tests cover nominal, degraded, and rejected-input
   paths;
4. a named baseline and fixed-seed evaluation are documented;
5. the default import remains free of legacy, experimental, console, and heavy
   optional dependencies; and
6. known limitations are recorded without implying real-world certification.

Experimental work additionally needs reproducible configuration and provenance
before promotion to beta. Standalone Monte Carlo uses at most 31 workers and
must not nest a process pool under pytest-xdist.
