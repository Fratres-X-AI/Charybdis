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
python run_sim.py
python run_sim.py --montecarlo 15
pytest -q -m "not console"
```

## Repository layout

```
Charybdis/
├── charybdis/              # installable Python package (active development)
│   ├── fusion.py           # hybrid 8D surface/submerged sensor fusion
│   ├── patrol.py           # waypoint patrol executor
│   ├── sensors.py          # abstract sensor measurements
│   ├── modes.py            # surface / submerged mode management
│   ├── navigator.py        # GDI fusion loop (TERCOM + EKF + PF)
│   ├── ekf.py / pf.py / tercom.py / ins.py / ...
│   ├── simulation.py       # end-to-end sim harness
│   ├── evaluate.py         # Monte-Carlo CEP / NEES
│   └── experimental/       # opt-in research modules (SLAM, swarm, NN)
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
| GDI nav | `Navigator`, `NavEstimate`, `NavEKF`, `TerrainParticleFilter` |
| Hybrid UUV | `HybridSensorFusion`, `PatrolExecutor`, `SensorPacket`, `NavMode` |
| Simulation | `run_simulation`, `run_montecarlo` |

```python
from charybdis import (
    SimConfig, Navigator, HybridSensorFusion, PatrolExecutor, run_simulation,
)
```

Submodule imports remain valid for advanced use:

```python
from charybdis.stress import run_stress_harness
from charybdis.bathy import load_npz
```

### Experimental (`import charybdis.experimental`)

Unstable, opt-in modules. Not loaded by default `import charybdis`.

```python
from charybdis.experimental import run_swarm, init_slam
from charybdis.experimental.nn_matcher import match_position, train
```

Legacy shims at `charybdis.slam`, `charybdis.swarm`, and `charybdis.nn_matcher`
still work but emit `DeprecationWarning` — prefer `charybdis.experimental.*`.

### Paused console (`console/`)

The Streamlit UUV tactical console is isolated under `console/` and not part of
active development. See [`console/README.md`](console/README.md).

## Hybrid navigation layer

For harbor-patrol UUV software (no hardware coupling):

- **`sensors.py`** — abstract GPS, IMU, depth, DVL, bathymetry inputs
- **`modes.py`** — surface vs submerged with depth hysteresis
- **`fusion.py`** — conservative 8D EKF-style fusion with chi-square gating
- **`patrol.py`** — waypoint routes with heading-aware LOS guidance

GPS is accepted in surface mode; bathymetry primarily in submerged mode.

## GDI navigation stack

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
