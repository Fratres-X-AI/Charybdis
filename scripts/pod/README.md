# RunPod / ephemeral GPU helpers

These scripts are **operational tooling**, not the product API.

- Prefer product scripts in `scripts/` (`stress_run.py`, `pmf_sweep.py`, `mc_real_region.py`, …).
- Hard rule: max **31** workers for standalone MC; never nest pools under `pytest -n`.
- Paths often assume `/workspace/Charybdis` on RunPod images.

See `docs/MATURITY.md` (CI / pod policy), `docs/KNOWN_LIMITS.md`, and `docs/MISSION.md`.

## Bronze / A100 helpers

```bash
bash scripts/pod/launch_bronze_military.sh   # full Phase 2 eng+release
bash scripts/pod/launch_bronze_beach.sh      # beach pytest + eng matrix
bash scripts/pod/poll_bronze.sh
bash scripts/pod/pull_pod_bronze.sh
```


## Finish today (RunPod)

```bash
cd /workspace
git clone https://github.com/Fratres-X-AI/Charybdis.git   # or git pull
cd Charybdis
bash scripts/pod/pod_today.sh              # synthetic MC + stress + full pytest
bash scripts/pod/pod_today.sh /path/tile.npz # same, on real bathy tile
```

Log: `pod_today.log`. Required gates: Phase 1–3 green; Phase 4 documents CEP.  
Optional: `TODAY_TRAIN=1 bash scripts/pod/pod_today.sh` for GPU NN retrain.
