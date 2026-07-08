# Charybdis GDI — GPS-Denied Interceptor

Terrain-aided inertial navigation for a GNSS-denied interceptor. Charybdis fuses a
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

- **INS / dead-reckoning** (`ins.py`): integrates specific force; drifts unbounded when unaided — the baseline Charybdis beats.
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

| metric | INS only | Charybdis EKF | Particle filter |
|---|---|---|---|
| RMSE | ~920 m | ~20 m | ~22 m |
| final error | ~1980 m | ~7 m | ~7 m |

Monte-Carlo (8 seeds): EKF CEP50 **24 m** / CEP95 **59 m**, PF CEP50 **27 m**; EKF **NEES ≈ 1.9** (consistent, ~2.0 ideal). With a 450 m injected initial error and TERCOM disabled (TRN only), the PF converges to **<20 m** while the EKF can settle **80–95 m** off in a wrong terrain minimum — the particle filter's key advantage.

![map](outputs/map.png)
![error](outputs/error.png)

## Layout

```
charybdis/
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

# Charybdis — UUV TCM Tactical Console

A second, self-contained deliverable: a real-time **Streamlit + Plotly**
"Tactical Command Console" for a **GPS-denied unmanned underwater vehicle**.
It runs dead-reckoned inertial navigation (noisy DVL + drifting IMU), grows a
2-D error-covariance ellipse, and bounds the drift with **Terrain Contour
Matching** fixes computed by real normalized cross-correlation of the seabed
profile against a stored bathymetric map — now wrapped in a full **autonomy
layer** (mission FSM, adaptive fixing, endurance, acoustic management, terrain
avoidance) plus contested-environment behaviour (spoof resistance, contact
tracking).

- `charybdis_core.py` — pure-NumPy GNC engine (true physics, sensor models, dead-reckoning covariance, TCM correlation + spoof-resistant gating, active-ping override) that orchestrates the subsystem modules. No UI coupling.
- `charybdis_sensors.py` — **Janus 4-beam DVL** (per-beam Doppler projection, least-squares velocity reconstruction, scale-factor error, beam dropout → bottom-lock loss) and an **IMU** with a random-walk heading (attitude) bias that mis-resolves body velocity into the nav frame — the dominant dead-reckoning error.
- `charybdis_autonomy.py` — mission **FSM** `PATROL → INSPECT → TCM FIX → RTB → ON STATION`, normalised **energy/endurance** model (hotel + cubic propulsion + sonar) that forces return-to-base, **adaptive terrain fixing** (divert to the nearest contour when 1σ error exceeds a trigger), passive-first **active-acoustic management** (radiate only when badly lost *and* the threat tolerates it), and reactive **vertical terrain avoidance** (forward-look bottom-following).
- `charybdis_tracking.py` — **multi-contact tracking**: independent constant-velocity Kalman filters fed noisy range/bearing from the *believed* ownship position, so track quality degrades with nav drift.
- `charybdis_bathy.py` — **real bathymetry loading** (`.npy` / `.npz` / GeoTIFF-if-`rasterio`) as a bilinearly-sampled provider swapped in via `set_bathymetry`; falls back to the synthetic map.
- `charybdis_console.py` — military-spec console: live tactical plot (true vs INS path, moving 1σ ellipse, contours, tracked contacts, spoof zone, waypoint, asset), sidebar controls (tidal / IMU drift / DVL noise + beam dropout, autonomy toggles, threat level, contact count, spoof injection), **EMERGENCY ACOUSTIC PING**, a two-row telemetry matrix (deflection, drift accel, counter-detection risk, uncertainty, mission state, endurance, seabed clearance, contacts), seabed-clearance chart, and a scrolling tactical log. Asynchronous ~5 Hz loop.

The nav filter is strictly isolated from ground truth; TCM/ping fixes are the
only re-coupling. Error growth is the exact constant-velocity covariance model
(position variance ~ cubic in time), so the plotted ellipse is statistically
consistent with the true deflection, and collapses to ~0 on each fix.
Autonomy/tracking run on a **separate RNG stream**, so the seeded nav-sensor
noise (and the classic non-autonomous behaviour) is bit-for-bit unchanged.

### Delivered from the enhancement list
Real bathymetry loading · adaptive/active TCM triggering · improved error-ellipse
+ loudness-based counter-detection risk · DVL beam-geometry + scale + IMU bias
fusion upgrade · mission planner FSM · adaptive TCM · terrain avoidance · energy
/ endurance · multi-contact tracking · active-acoustic management · spoofing +
detection · learned NN TCM · online terrain SLAM · multi-agent coordination ·
ROS2 bridge · GEBCO NetCDF ingestion.

### Bathymetric nodes
Trench Alpha `(35, 25)` · Ridge Bravo `(70, 85)` · Seamount Charlie `(100, 105)`, lock radius `5.0 u`.

### Run

```bash
uv add streamlit numpy plotly pandas          # or: pip install -r requirements.txt
uv run streamlit run charybdis_console.py      # or: streamlit run charybdis_console.py
python charybdis_core.py                         # headless autonomous-mission self-test
pytest tests/test_charybdis_uuv.py tests/test_upgrade2.py tests/test_final4.py -q
python scripts/benchmark_15of15.py          # SLAM / swarm / NN metrics (NN needs torch)
bash scripts/ros2_smoke.sh                  # Docker + ROS2 jazzy (optional)
python scripts/train_tcm_nn.py              # GPU train -> models/tcm_cnn.pt
```

> Research/simulation only.
