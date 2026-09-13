# Charybdis mission

## Purpose

Charybdis is a hybrid-first research and simulation platform for
surface/submerged UUV navigation and patrol guidance in GPS-limited
environments.

The primary deliverable is a small, auditable software boundary that:

- accepts hardware-neutral IMU, GPS, depth, velocity, and bathymetry inputs;
- maintains a state estimate and explicit covariance;
- handles surface/submerged mode transitions conservatively;
- rejects statistically inconsistent measurements;
- exposes bounded diagnostics for degraded navigation;
- converts an immutable navigation state into waypoint guidance; and
- supports deterministic simulation and reproducible fixed-seed evaluation.

Correctness, uncertainty honesty, failure visibility, and reproducibility take
priority over feature count.

## Scope priorities

First priority is the `charybdis.hybrid` path and the symbols exported from
`charybdis/__init__.py`.

Second priority is simulation and evaluation support needed to test that path,
including terrain-profile matching, named synthetic harbor scenarios,
confidence-bounded Monte Carlo gates, provenance-tracked real-map
characterization, and auditable validation artifacts.

The interceptor estimator stack in `charybdis.legacy` is maintained for
comparative research and existing internal use. It is not the architecture for
new hybrid UUV work.

Neural matching, SLAM, and swarm research remain under
`charybdis.experimental`. The repository-level console is paused and excluded
from the wheel.

## Integration philosophy

Charybdis stops at navigation state and patrol guidance. Integrators own:

- sensor drivers, calibration, clock synchronization, and frame transforms;
- map acquisition, datum checks, and data quality;
- mission management and operator authorization;
- obstacle and collision avoidance;
- control allocation, actuators, and vehicle dynamics;
- watchdogs, independent safety monitors, and emergency behavior; and
- cybersecurity controls for deployed systems.

Examples model these seams but do not implement a deployable vehicle stack.

## Non-goals

The project does not currently claim:

- real-world vehicle, harbor, flight, or dive validation;
- safety, regulatory, or mission certification;
- hardware-in-the-loop qualification;
- guaranteed performance on arbitrary bathymetry or sensor faults;
- treating GEBCO matcher characterization as field or sea-trial evidence;
- a complete autonomy or vehicle-control system;
- stable APIs for experimental modules; or
- support for the paused console as part of the released package.

Synthetic Monte Carlo results are engineering evidence for the modeled
scenarios only. A real bathymetry grid improves map realism but does not make
synthetic profiles, priors, and noise into real-world navigation validation.

## Engineering rules

1. Keep `import charybdis` hybrid-focused and free of legacy, experimental,
   console, and optional deep-learning imports.
2. Use immutable input and output contracts across integration boundaries.
3. Preserve covariance and rejection diagnostics; do not hide estimator
   uncertainty behind a position-only interface.
4. Prefer conservative holds and explicit rejection statuses to silent
   fallback behavior.
5. Declare gates before release runs and record their confidence intervals,
   seed sets, configuration, source revision, runtime versions, and output
   artifacts.
6. Cap standalone Monte Carlo at 31 workers and never nest pools under
   pytest-xdist.
7. Label simulated, experimental, and unvalidated behavior accurately.

## Evidence and promotion

Feature promotion requires a named use case, documented failure behavior,
fast regression coverage, and reproducible evaluation against a stated
baseline. Stable research interfaces additionally require an uncertainty
contract and no known silent failure path in covered scenarios.

Promotion is an API and evidence decision, not a claim of operational readiness.
Detailed labels are in [`MATURITY.md`](MATURITY.md); reproducible commands and
limitations are in [`VALIDATION.md`](VALIDATION.md); GPU pod operations are in
[`REMOTE_VALIDATION.md`](REMOTE_VALIDATION.md).
