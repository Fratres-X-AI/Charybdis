# Feature maturity

Labels:

| Label | Meaning |
|-------|---------|
| **Stable** | Core path; regressions blocked by CI; safe default API |
| **Beta** | Useful and tested; API may still move |
| **Experimental** | Research / opt-in; may be wrong, slow, or sim-only |
| **Deprecated** | Kept for compatibility; do not extend |

See [`MISSION.md`](MISSION.md) for promotion rules.

## GDI package (`charybdis/`)

| Module | Maturity | Notes |
|--------|----------|-------|
| `config`, `terrain`, `trajectory` | Stable | Synthetic DEM + truth path |
| `imu`, `ins`, `tercom` | Stable | Sensor + dead-reckoning + TERCOM |
| `ekf` | Stable | Joseph-form EKF, TRN + position updates |
| `pf` | Stable | Bootstrap SIR; exposes `pos_cov` / `pos_std` |
| `pmf` | Beta | Marginalized point-mass filter; strong on large init |
| `navigator` | Stable | Fusion loop; exposes `NavEstimate` |
| `simulation`, `evaluate` | Stable | End-to-end + MC CEP/NEES |
| `pcrb`, `stress`, `parallel` | Beta | Bounds, stress gates, worker caps |
| `imu_model` | Beta | Allan / grade presets |
| `bathy` | Beta | GEBCO / GeoTIFF / grid → `Terrain` |
| `experimental.nn_matcher` | Experimental | SO(2) Siamese; needs estimated-pose wiring |
| `experimental.slam` | Experimental | Submap GICP; not in default Navigator |
| `experimental.swarm` | Experimental | OWTT multi-agent; pod-validated MC |

## UUV root modules

| Module | Maturity | Notes |
|--------|----------|-------|
| `charybdis_core` | Beta | UUV GNC engine; console spine |
| `charybdis_sensors` | Beta | Janus DVL + IMU bias |
| `charybdis_autonomy` | Beta | Mission FSM, adaptive TCM, energy |
| `charybdis_tracking` | Beta | Multi-contact CV Kalman |
| `charybdis_console` | Beta | Streamlit tactical UI |
| `charybdis_bathy` | Beta | Callable bathymetry for UUV map scale |
| `charybdis_nn` | Experimental | UUV-scale Siamese TCM (`tcm_cnn.pt`) |
| `charybdis_slam` | Experimental | Correlation submap SLAM |
| `charybdis_swarm` | Experimental | Core-based multi-agent |

## Integrations

| Path | Maturity | Notes |
|------|----------|-------|
| `ros2_ws/` | Experimental | Optional bridge; smoke via `scripts/ros2_smoke.sh` |
| `scripts/pod/` | Operational tooling | Ephemeral RunPod helpers; not product API |

## CI policy

- **Always:** compileall + fast pytest (slow integration tests skipped on `GITHUB_ACTIONS`)
- **Pod / local opt-in:** `@pytest.mark.slow` or `RUN_SLOW=1`; stress / PMF sweeps; GPU NN train
- **Worker hard rule:** max 31 processes for standalone MC; never nest pools under pytest xdist
