# Architecture

## Two stacks, one repo

```
┌─────────────────────────────────────────────┐
│  charybdis/          GDI nav library        │
│  (INS, TERCOM, EKF, PF, PMF, MC, bathy)     │
│         │                                   │
│         └── experimental/  (NN, SLAM, swarm)│
└─────────────────────────────────────────────┘
┌─────────────────────────────────────────────┐
│  charybdis_*.py      UUV tactical spine     │
│  core ← sensors, autonomy, tracking         │
│  console (Streamlit)                        │
│  experimental: _nn, _slam, _swarm           │
└─────────────────────────────────────────────┘
```

They share the GPS-denied terrain-aiding problem. They do **not** yet share a single runtime. Bridge intentionally via small APIs (`NavEstimate`, bathymetry loaders), not by merging files blindly.

## Target layout (Phase 1 progress)

```
charybdis/                 # installable GDI library
  __init__.py              # Stable/Beta exports only
  experimental/            # opt-in research modules
  *.py                     # nav + data + eval
apps via root: run_sim.py; UUV console (paused): console/charybdis_console.py
scripts/                   # product MC / train / stress
scripts/pod/               # RunPod one-offs
docs/                      # MISSION, MATURITY, ARCHITECTURE
tests/                     # pytest (slow skipped on CI)
ros2_ws/                   # optional
models/                    # trained weights
```

## Navigator contract

`Navigator.estimate()` returns a `NavEstimate` (position, 2×2 covariance, source filter, optional Neff). Autonomy and UI layers should consume this instead of reaching into filter internals.

## Experimental import

```python
from charybdis.experimental import build_model, run_swarm, init_slam
```

Default `import charybdis` must not load torch or experimental side effects.
