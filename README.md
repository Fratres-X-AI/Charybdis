# Charybdis — GPS-Denied Terrain-Aided Navigation

**Current focus:** the core GPS-denied navigation stack in the `charybdis/` package
(INS + TERCOM/TRN + EKF + particle filter), with honest Monte-Carlo evaluation.

**Paused:** the UUV tactical Streamlit console and autonomy layer live under
[`console/`](console/) and are not part of active development until core navigation
is in good shape. See [`console/README.md`](console/README.md).

See also [`docs/MISSION.md`](docs/MISSION.md), [`docs/MATURITY.md`](docs/MATURITY.md),
and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## GDI stack

Terrain-aided inertial navigation for a GNSS-denied interceptor. Charybdis fuses a
strapdown **INS (dead-reckoning)** with **TERCOM** terrain-contour matching and a
recursive **terrain-referenced (TRN)** update inside an **Extended Kalman Filter**,
so the vehicle keeps an accurate fix with no GPS. A **terrain-aided particle
filter** (and optional **PMF**) runs in parallel as a non-Gaussian estimator, and a
Monte-Carlo harness reports CEP and filter-consistency (NEES) metrics.

## How it works

```
 IMU (accel, gyro) ─► Strapdown INS ─► EKF predict ─┐
                                                     ├─► fused state (pos, vel, bias)
 Radar alt + Baro  ─► ground elevation ─► TERCOM ────┤        │
                                        └► TRN slope ─┘        ▼
   stored DEM ◄──────────── correlate / gradient ──────► position fix
```

- **INS / dead-reckoning** (`ins.py`): integrates specific force; drifts unbounded when unaided — the baseline Charybdis beats.
- **Terrain / DEM** (`terrain.py`): synthetic fractal elevation map with bilinear query and slope.
- **TERCOM** (`tercom.py`): buffers a strip of measured ground elevations, slides it over the DEM, and picks the horizontal offset with minimum mean-absolute-difference → absolute position fix (sub-cell refined, with covariance from the correlation surface).
- **TRN update** (`ekf.py`): recursive single-point update using measured terrain elevation vs. DEM, Jacobian = local terrain slope.
- **EKF** (`ekf.py`): state `[px, py, vx, vy, bax, bay]`, IMU-driven prediction, Joseph-form covariance, χ² innovation gating.
- **Particle filter** (`pf.py`): bootstrap SIR over the same 6-state model. Weights come from the *exact* (non-linearised) terrain-elevation likelihood, so it represents the multi-modal position posterior instead of a single Gaussian. Systematic resampling with floored roughening prevents impoverishment; TERCOM fixes are χ²-gated and used to relocalise the cloud (with velocity recovered by differencing consecutive fixes). This is what lets it recover from large initial errors the EKF cannot.
- **Navigator** (`navigator.py`): fusion loop; exposes **`NavEstimate`** (pos + 2×2 cov) for downstream consumers.
- **Evaluation** (`evaluate.py`): Monte-Carlo over seeds → CEP50/CEP95, mean RMSE, and EKF **NEES** (a 2-DOF-consistent filter averages ≈ 2.0).

## Run

```bash
pip install -r requirements.txt
python run_sim.py                 # writes outputs/map.png, outputs/error.png
python run_sim.py --duration 300 --seed 12
python run_sim.py --montecarlo 15 # CEP / NEES evaluation table
python scripts/mc_real_region.py  # synthetic MC; pass --npz for a real tile
python scripts/stress_run.py      # stress harness
pytest -q                         # core navigation tests (console tests excluded)
```

Console tests (paused layer): `RUN_CONSOLE=1 pytest -m console -q`

## Representative results (180 s, 50 Hz)

| metric | INS only | Charybdis EKF | Particle filter |
|---|---|---|---|
| RMSE | ~920 m | ~20 m | ~22 m |
| final error | ~1980 m | ~7 m | ~7 m |

Monte-Carlo (8 seeds): EKF CEP50 **24 m** / CEP95 **59 m**, PF CEP50 **27 m**; EKF **NEES ≈ 1.9** (consistent, ~2.0 ideal). With a 450 m injected initial error and TERCOM disabled (TRN only), the PF converges to **<20 m** while the EKF can settle **80–95 m** off in a wrong terrain minimum — the particle filter's key advantage.

![map](outputs/map.png)
![error](outputs/error.png)

## Layout

```
charybdis/                 # Core GDI library (active development)
  navigator.py             # NavEstimate + fusion loop
  ekf.py / pf.py / pmf.py / tercom.py / ins.py
  bathy.py                 # GEBCO / grid loaders
  experimental/            # NN matcher, SLAM, swarm (opt-in)
console/                   # UUV tactical console + autonomy (PAUSED)
docs/                      # MISSION, MATURITY, ARCHITECTURE
scripts/                   # MC / stress / train / pod helpers
tests/                     # Core nav tests; console tests marked @console
run_sim.py
```

Experimental imports (core package):

```python
from charybdis.experimental import run_swarm, init_slam
from charybdis.experimental.nn_matcher import match_position, train
```

## UUV console (paused)

The Streamlit tactical console, autonomy FSM, multi-contact tracking, learned TCM
CNN, SLAM, and swarm modules were moved from the repo root into `console/`. They
remain in the repository but are isolated until the core navigation stack is
production-ready.

To run when resuming work on that layer:

```bash
streamlit run console/charybdis_console.py
python console/charybdis_core.py
pytest -m console -q
```

> Research/simulation only. Feature maturity: [`docs/MATURITY.md`](docs/MATURITY.md).
