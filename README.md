<p align="center">
  <img src="docs/assets/charybdis-hero.png" alt="Charybdis hybrid UUV navigation" width="920">
</p>

# Charybdis

Hybrid-first navigation and patrol research for surface/submerged UUVs.
Hardware-neutral sensor contracts, conservative 8-state fusion, bathymetric
terrain aiding, navigation-health diagnostics, and waypoint guidance — with
reproducible validation gates and an explicit production integration boundary.

Charybdis is research and simulation software. It is not certified vehicle
software, a safety controller, or evidence of real-world mission validation.

## Validation snapshot

Current `main` — see [`docs/VALIDATION.md`](docs/VALIDATION.md) and
[`docs/KNOWN_LIMITS.md`](docs/KNOWN_LIMITS.md).

| Gate | Result |
|------|--------|
| CI | PASS on `main` |
| Mission engineering | PASS 6/6 @ 256 runs |
| Holdout harbor + deep | PASS 7/7 each @ 256 runs |
| Harbor + deep release | PASS 7/7 each @ 256 runs |
| NOAA Monterey highres | PASS — CEP95 9.78 m, 256/256 accepted |
| Promoted matcher | `models/tcm_so2.pt` |

Release-tier CPU validation artifacts:
`artifacts/pod_h200_final_20260717T143729Z/`. Verify locally:

```bash
bash scripts/pod/verify_release_cpu.sh
```

Optional GPU matcher retraining is documented in [`docs/REMOTE_VALIDATION.md`](docs/REMOTE_VALIDATION.md).
It is not required for the release CPU gates above.

## Quick start

Python 3.11+:

```bash
python -m pip install -e ".[dev]"
python -m pytest tests/test_architecture.py
python examples/run_hybrid_patrol.py
python examples/verify_pilot_replay.py
```

## Hybrid-first public API

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

Contract: [`docs/STABLE_API.md`](docs/STABLE_API.md).

## Documentation

| Document | Purpose |
|----------|---------|
| [`docs/README.md`](docs/README.md) | Documentation index |
| [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md) | First integration walkthrough |
| [`docs/VALIDATION.md`](docs/VALIDATION.md) | CI, Phase 2, bathymetry gates |
| [`docs/REMOTE_VALIDATION.md`](docs/REMOTE_VALIDATION.md) | Optional cloud GPU workflows |
| [`docs/INTEGRATION_HANDOFF.md`](docs/INTEGRATION_HANDOFF.md) | Pilot handoff bundle |
| [`docs/KNOWN_LIMITS.md`](docs/KNOWN_LIMITS.md) | What PASS does not mean |

## License

Proprietary and confidential. See [`LICENSE`](LICENSE).
