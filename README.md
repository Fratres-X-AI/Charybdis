# Syren GDI — GPS-Denied Interceptor

Terrain-aided inertial navigation for a GNSS-denied interceptor. Syren fuses a
strapdown **INS (dead-reckoning)** with **TERCOM** terrain-contour matching and a
recursive **terrain-referenced (TRN)** update inside an **Extended Kalman Filter**,
so the vehicle keeps an accurate fix with no GPS.

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

## Run

```bash
pip install -r requirements.txt
python run_sim.py                 # writes outputs/map.png, outputs/error.png
python run_sim.py --duration 300 --seed 12
pytest -q
```

## Representative result (180 s, 50 Hz)

| metric | INS only | Syren EKF |
|---|---|---|
| RMSE | ~920 m | ~20 m |
| final error | ~1980 m | ~7 m |

~280× drift reduction; EKF error stays inside its 3σ bound.

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
  navigator.py    full nav loop
  simulation.py   end-to-end harness
run_sim.py        CLI + plots
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
