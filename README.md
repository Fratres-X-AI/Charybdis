# Syren GDI — GPS-Denied Interceptor

Terrain-aided inertial navigation for a GNSS-denied interceptor. Syren fuses a
strapdown **INS (dead-reckoning)** with **TERCOM** terrain-contour matching and a
recursive **terrain-referenced (TRN)** update inside an **Extended Kalman Filter**,
so the vehicle keeps an accurate fix with no GPS. A **terrain-aided particle
filter** runs in parallel as a non-Gaussian estimator, and a Monte-Carlo harness
reports CEP and filter-consistency (NEES) metrics.

## How it works

```
 IMU (accel, gyro) ─► Strapdown INS ─► EKF predict ─┐
                                                     ├─► fused state (pos, vel, bias)
 Radar alt + Baro  ─► ground elevation ─► TERCOM ────┤        │
                                        └► TRN slope ─┘        ▼
   stored DEM ◄──────────── correlate / gradient ──────► position fix
```

- **INS / dead-reckoning** (`ins.py`): integrates specific force; drifts unbounded when unaided — the baseline Syren beats.
- **Terrain / DEM** (`terrain.py`): synthetic fractal elevation map with bilinear query and slope.
- **TERCOM** (`tercom.py`): buffers a strip of measured ground elevations, slides it over the DEM, and picks the horizontal offset with minimum mean-absolute-difference → absolute position fix (sub-cell refined, with covariance from the correlation surface).
- **TRN update** (`ekf.py`): recursive single-point update using measured terrain elevation vs. DEM, Jacobian = local terrain slope.
- **EKF** (`ekf.py`): state `[px, py, vx, vy, bax, bay]`, IMU-driven prediction, Joseph-form covariance, χ² innovation gating.
- **Particle filter** (`pf.py`): bootstrap SIR over the same 6-state model. Weights come from the *exact* (non-linearised) terrain-elevation likelihood, so it represents the multi-modal position posterior instead of a single Gaussian. Systematic resampling with floored roughening prevents impoverishment; TERCOM fixes are χ²-gated and used to relocalise the cloud (with velocity recovered by differencing consecutive fixes). This is what lets it recover from large initial errors the EKF cannot.
- **Evaluation** (`evaluate.py`): Monte-Carlo over seeds → CEP50/CEP95, mean RMSE, and EKF **NEES** (a 2-DOF-consistent filter averages ≈ 2.0).

## Run

```bash
pip install -r requirements.txt
python run_sim.py                 # writes outputs/map.png, outputs/error.png
python run_sim.py --duration 300 --seed 12
python run_sim.py --montecarlo 15 # CEP / NEES evaluation table
pytest -q
```

## Representative results (180 s, 50 Hz)

| metric | INS only | Syren EKF | Particle filter |
|---|---|---|---|
| RMSE | ~920 m | ~20 m | ~22 m |
| final error | ~1980 m | ~7 m | ~7 m |

Monte-Carlo (8 seeds): EKF CEP50 **24 m** / CEP95 **59 m**, PF CEP50 **27 m**; EKF **NEES ≈ 1.9** (consistent, ~2.0 ideal). With a 450 m injected initial error and TERCOM disabled (TRN only), the PF converges to **<20 m** while the EKF can settle **80–95 m** off in a wrong terrain minimum — the particle filter's key advantage.

![map](outputs/map.png)
![error](outputs/error.png)

## Layout

```
syren/
  config.py       tunable parameters
  terrain.py      DEM + interpolation/gradient
  trajectory.py   truth flight path
  imu.py          IMU + altimeter sensor models
  ins.py          strapdown dead-reckoning
  tercom.py       terrain-contour matching
  ekf.py          EKF fusion (TRN + TERCOM)
  pf.py           terrain-aided particle filter
  navigator.py    full nav loop (INS + EKF + PF)
  simulation.py   end-to-end harness
  evaluate.py     Monte-Carlo CEP / NEES
run_sim.py        CLI + plots + --montecarlo
tests/            pytest suite
```

---

# Black Sea Sentry — UUV TCM Tactical Console

A second, self-contained deliverable: a real-time **Streamlit + Plotly**
"Tactical Command Console" for a **GPS-denied unmanned underwater vehicle**.
It runs dead-reckoned inertial navigation (noisy DVL + drifting IMU), grows a
2-D error-covariance ellipse, and bounds the drift with **Terrain Contour
Matching** fixes computed by real normalized cross-correlation of the seabed
profile against a stored bathymetric map.

- `sentry_core.py` — pure-NumPy GNC engine (true physics, sensor models, dead-reckoning covariance, TCM correlation, active-ping override). No UI coupling.
- `blacksea_sentry.py` — military-spec console: live tactical bathymetric plot (true vs INS path, moving 1σ error ellipse, nodes, waypoint, asset), sidebar sliders (tidal current, IMU drift, DVL noise), **EMERGENCY ACOUSTIC PING**, telemetry matrix (deflection, drift acceleration, counter-detection risk), and a scrolling tactical log. Runs an asynchronous ~5 Hz loop.

The nav filter is strictly isolated from ground truth; TCM/ping fixes are the
only re-coupling. Error growth is the exact constant-velocity covariance model
(position variance ~ cubic in time), so the plotted ellipse is statistically
consistent with the true deflection, and collapses to ~0 on each fix.

### Bathymetric nodes
Trench Alpha `(35, 25)` · Ridge Bravo `(70, 85)` · Seamount Charlie `(100, 105)`, lock radius `5.0 u`.

### Run

```bash
uv add streamlit numpy plotly pandas          # or: pip install -r requirements.txt
uv run streamlit run blacksea_sentry.py        # or: streamlit run blacksea_sentry.py
python sentry_core.py                           # headless GNC self-test
pytest tests/test_sentry.py -q
```

> Research/simulation only.
