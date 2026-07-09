# UUV Tactical Console (Paused)

This folder holds the **UUV tactical Streamlit console** and **autonomy layer**
that were previously at the repository root as `charybdis_*.py` modules.

**Status:** Paused until the core GPS-denied navigation stack (`charybdis/`) is
in good shape. Nothing here is deleted — it is isolated from active development.

## Modules

| File | Role |
|---|---|
| `charybdis_core.py` | Pure-NumPy GNC engine (physics, sensors, TCM, autonomy orchestration) |
| `charybdis_console.py` | Streamlit + Plotly tactical command console |
| `charybdis_sensors.py` | DVL + IMU sensor models |
| `charybdis_tracking.py` | Multi-contact tracking |
| `charybdis_autonomy.py` | Mission FSM, endurance, terrain avoidance |
| `charybdis_bathy.py` | Real bathymetry loaders for the console (not `charybdis/bathy.py`) |
| `charybdis_slam.py` | Online terrain SLAM (experimental) |
| `charybdis_swarm.py` | Multi-agent coordination (experimental) |
| `charybdis_nn.py` | Learned TCM CNN (experimental; needs `torch`) |

## Run (when resuming)

```bash
pip install -r requirements.txt
streamlit run console/charybdis_console.py
python -m console.charybdis_core          # headless self-test
pytest tests/test_charybdis_uuv.py -q     # console tests (RUN_CONSOLE=1 on CI)
```

Core navigation work uses `run_sim.py`, `pytest -q` (default suite), and
`scripts/pod/` validation — not this folder.
