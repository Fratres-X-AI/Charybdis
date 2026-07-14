<p align="center">
  <img src="docs/assets/charybdis-hero.png" alt="Charybdis hybrid UUV navigation" width="920">
</p>

# Charybdis

Hybrid-first navigation and patrol research for surface/submerged UUVs.
Hardware-neutral sensor contracts, conservative 8-state fusion, bathymetric
terrain aiding, navigation-health diagnostics, and waypoint guidance — with
reproducible validation gates and an explicit production integration boundary.

The repository also retains a maintained legacy interceptor stack and opt-in
experimental research. Neither is imported by the package root.

Charybdis is research and simulation software. It is not certified vehicle
software, a safety controller, or evidence of real-world mission validation.

## Validation snapshot

Latest L40S pod validation at `164ea68` (31-worker CPU validation):

| Tier | Result |
|------|--------|
| CI | PASSED on `main` (`29357300247`) |
| Integration grade | Harbor 7/7 + deep 7/7 PASS @ 64 seeds/scenario |
| Release matrix | Harbor 7/7 + deep 7/7 PASS @ 256 seeds/scenario |
| Deep long blackout | PASS, CEP95 ~1.16 m in 512-run worst sweep |
| Real-bathymetry (GEBCO tile) | PASS engineering + release; coarse characterization only |

Artifacts: `artifacts/pod_l40s_pull_20260714T180953Z` — see
[`docs/VALIDATION.md`](docs/VALIDATION.md) for procedures and limitations.

## Install

Python 3.11 or newer is required. Authorized contributors can install the
package from a repository checkout:

```bash
python -m pip install -e .
```

For linting, typing, and tests:

```bash
python -m pip install -e ".[dev]"
```

Optional dependency groups include `nn`, `gebco`, and `console`. Installing a
group does not change the default import boundary.

## Run the examples

Each example is deterministic and runs after the editable install:

```bash
python examples/run_hybrid_patrol.py
python examples/adapter_pattern.py
python examples/terrain_profile_matching.py
python examples/degraded_sensors.py
python examples/legacy_interceptor.py
```

See [`examples/README.md`](examples/README.md) for the purpose and operational
boundary of each example.

Start with [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md) for the runtime
walkthrough, [`docs/STABLE_API.md`](docs/STABLE_API.md) for the supported API
contract, [`docs/INTEGRATION_HANDOFF.md`](docs/INTEGRATION_HANDOFF.md) for the
handoff bundle, and [`docs/PRODUCTION_INTEGRATION.md`](docs/PRODUCTION_INTEGRATION.md)
before connecting logs or hardware.

## Hybrid-first public API

`import charybdis` exposes only the curated hybrid API:

- `__version__`
- `BathymetryMap`, `TerrainProfileMatcher`
- `NavMode`, `SensorPacket`
- `HybridNavState`, `HybridSensorFusion`
- `HybridNavigator`, `HybridStepResult`
- `PatrolExecutor`

The root deliberately does not export configuration, simulation, legacy, or
experimental symbols. Detailed hybrid measurement and configuration types are
available from `charybdis.hybrid`.
`docs/STABLE_API.md` is the compatibility contract for these imports.

```python
from charybdis import (
    HybridNavigator,
    HybridSensorFusion,
    NavMode,
    PatrolExecutor,
    SensorPacket,
)
from charybdis.hybrid import (
    DepthMeasurement,
    GpsMeasurement,
    ImuMeasurement,
    PatrolRoute,
    Waypoint,
)
```

`HybridNavigator.step()` is the recommended integration point. It processes
one `SensorPacket`, then generates guidance from the resulting immutable
`HybridNavState`.

## Explicit secondary APIs

The maintained interceptor stack must be imported explicitly:

```python
from charybdis.config import SimConfig
from charybdis.legacy import NavEstimate, Navigator
from charybdis.simulation import run_simulation
```

Experimental modules are unstable and opt-in:

```python
from charybdis.experimental import init_slam, run_swarm
from charybdis.experimental.nn_matcher import match_position
```

There are no root-level compatibility shims for legacy or experimental
features. Importing `charybdis` does not load `charybdis.legacy`,
`charybdis.experimental`, or PyTorch.

## Runtime architecture

The primary path is:

```text
sensor/log adapters
        |
        v
SensorPacket -> HybridSensorFusion -> HybridNavState
                                          |
                                          v
                                    PatrolExecutor
                                          |
                                          v
                                    PatrolCommand
```

GPS updates are accepted only while surfaced. Bathymetry fixes are accepted
only while submerged. Depth hysteresis controls mode selection by default;
route hints do not override authoritative depth outside the hysteresis band.
Measurement covariance is quality-scaled, innovations are chi-square gated,
and guidance commands zero horizontal velocity when navigation health or
uncertainty exceeds configured limits.

The library produces guidance, not actuator commands. Hardware drivers,
time synchronization, mission planning, collision avoidance, control
allocation, and safety interlocks remain integration responsibilities.

## Packaging boundary

The wheel contains the `charybdis` package. The paused Streamlit source under
`console/` is intentionally excluded from the wheel and is not part of the
hybrid runtime. See [`console/README.md`](console/README.md).

## Validation

Fast CI-equivalent commands, confidence gates, artifacts, provenance fields,
worker limits, and limitations are documented in
[`docs/VALIDATION.md`](docs/VALIDATION.md).

Start with:

```bash
python -m pytest tests/test_architecture.py
python -m pytest -m "not console"
```

On a prepared Linux pod, the canonical Phase 2 command is:

```bash
cd /workspace/Charybdis
bash scripts/pod/pod_hybrid_phase2.sh
```

Phase 2 requires a clean worktree. It runs seven synthetic scenarios at 64
engineering seeds and 256 release seeds per scenario, applies conservative 95%
confidence-bound gates, characterizes terrain matching on a projected GEBCO
2020 tile at both tiers, runs the retained legacy stress harness, and writes a
dependency freeze plus SHA-256 inventory. Standalone validation is capped at 31
workers.

These are internal software-release and research checks. A passing matrix or
GEBCO characterization is not a sea trial, operational acceptance, safety case,
real-world validation, or certification.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — components and import boundaries
- [`docs/MATURITY.md`](docs/MATURITY.md) — feature status and evidence levels
- [`docs/MISSION.md`](docs/MISSION.md) — project scope and non-goals
- [`docs/VALIDATION.md`](docs/VALIDATION.md) — reproducible validation procedures
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — authorized contribution workflow
- [`SECURITY.md`](SECURITY.md) — private vulnerability reporting

## License

Proprietary and confidential. See [`LICENSE`](LICENSE). No rights are granted
without prior written permission from Fratres-X-AI.
