# RunPod / ephemeral GPU helpers

These scripts are **operational tooling**, not the product API.

- Prefer product scripts in `scripts/` (`stress_run.py`, `pmf_sweep.py`, `mc_real_region.py`, …).
- Hard rule: max **31** workers for standalone MC; never nest pools under `pytest -n`.
- Paths often assume `/workspace/Charybdis` on RunPod images.

See `docs/MATURITY.md` (CI / pod policy) and `docs/MISSION.md`.
