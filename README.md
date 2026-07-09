# Charybdis

GPS-denied terrain-aided navigation for research and harbor-patrol UUV concepts.
Charybdis fuses inertial navigation with terrain contour matching (TERCOM/TRN),
extended Kalman and particle filters, and — for UUV work — a hybrid
surface/submerged sensor fusion layer with waypoint patrol execution.

## Install

```bash
git clone https://github.com/Fratres-X-AI/Charybdis.git
cd Charybdis
pip install -e .              # core package
pip install -e ".[dev]"       # + pytest
pip install -e ".[nn]"        # + torch (experimental NN matcher)
```

Or use `requirements.txt` for the full dev environment.

## Quick start

```bash
python examples/run_hybrid_patrol.py
python run_sim.py
python run_sim.py --montecarlo 15
pytest -q -m "not console"
```

## Repository layout

```
Charybdis/
├── charybdis/              # installable Python package
│   ├── config.py, terrain.py, trajectory.py, imu.py, ins.py, bathy.py
│   ├── hybrid/             # primary: surface/submerged UUV fusion + patrol
│   │   ├── fusion.py, patrol.py, sensors.py, modes.py
│   ├── legacy/             # isolated: interceptor TERCOM/EKF/PF/PMF stack
│   │   ├── navigator.py, ekf.py, pf.py, pmf.py, tercom.py
│   ├── simulation/         # end-to-end sim + hybrid harbor smoke sim
│   ├── evaluation/         # Monte-Carlo CEP / NEES + stress gates
│   └── experimental/       # opt-in research (SLAM, swarm, NN matcher)
├── console/                # UUV tactical console (PAUSED)
├── tests/                  # pytest suite
├── scripts/                # MC, stress, pod helpers
├── docs/                   # MISSION, MATURITY, ARCHITECTURE
├── run_sim.py              # primary simulation entry point
├── pyproject.toml
├── README.md
└── LICENSE
```

## Package API

### Stable / Beta (`import charybdis`)

| Area | Key types |
|------|-----------|
| Config | `SimConfig` |
| Terrain | `Terrain`, `generate_truth` |
| Hybrid UUV (primary) | `HybridSensorFusion`, `PatrolExecutor`, `SensorPacket`, `NavMode` |
| Legacy interceptor | `Navigator`, `NavEstimate`, `NavEKF`, `TerrainParticleFilter` |
| Simulation | `run_simulation`, `run_montecarlo` |

```python
from charybdis import (
    SimConfig, Navigator, HybridSensorFusion, PatrolExecutor, run_simulation,
)
```

Submodule imports for focused access:

```python
from charybdis.hybrid import HybridSensorFusion, PatrolExecutor
from charybdis.legacy import Navigator, NavEstimate
from charybdis.evaluation import run_stress_harness
from charybdis.bathy import load_npz
```

### Experimental (`import charybdis.experimental`)

Unstable, opt-in modules. Not loaded by default `import charybdis`.

```python
from charybdis.experimental import run_swarm, init_slam
from charybdis.experimental.nn_matcher import match_position, train
```

Use `charybdis.experimental.*` only — root-level shim files have been removed.

### Paused console (`console/`)

The Streamlit UUV tactical console is isolated under `console/` and not part of
active development. See [`console/README.md`](console/README.md).

## Hybrid navigation layer

For harbor-patrol UUV software (no hardware coupling), see `charybdis/hybrid/`:

- **`sensors.py`** — abstract GPS, IMU, depth, DVL, bathymetry inputs
- **`modes.py`** — surface vs submerged with depth hysteresis
- **`fusion.py`** — conservative 8D EKF-style fusion with chi-square gating
- **`patrol.py`** — waypoint routes with heading-aware LOS guidance
- **`simulation/hybrid.py`** — small harbor mission smoke sim:
  surface GPS → dive → submerged patrol → resurface GPS

GPS is accepted in surface mode; bathymetry primarily in submerged mode.

## Legacy interceptor stack

The original terrain-aided interceptor navigation lives in `charybdis/legacy/`:

```
 IMU ─► INS predict ─► EKF ─┬─ TERCOM (batch correlation fix)
 Radar/baro ─► TRN update ──┘         │
                                      ▼
                            Particle filter (parallel)
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`docs/MISSION.md`](docs/MISSION.md).

## Tests

```bash
pytest -q -m "not console"     # core + hybrid (CI default)
pytest -m console -q           # paused UUV console layer
RUN_SLOW=1 pytest -m slow -q   # stress / MC gates
```

## License

Proprietary — see [`LICENSE`](LICENSE). Research/simulation use only.
