# Remote validation helpers

Scripts for ephemeral cloud GPU instances. Not part of the installable package.
Run from **Git Bash** on the mission-control host.

Full guide: [`docs/REMOTE_VALIDATION.md`](../../docs/REMOTE_VALIDATION.md)

## Release verification (no GPU)

```bash
bash scripts/pod/verify_release_cpu.sh
```

## 2× H200 SXM — full pipeline (one command)

1. Rent **2× H200 SXM** on RunPod (PyTorch CUDA 12.x template, volume at `/workspace`).
2. Connect tab → copy **SSH over exposed TCP** (not `ssh.runpod.io`).
3. Edit credentials:

```bash
cp scripts/pod/pod_env.local.sh.example scripts/pod/pod_env.local.sh
# set POD_NAME, POD_HOST, POD_PORT, POD_KEY
```

4. Launch beginning → 100% green → artifact pull:

```bash
bash scripts/pod/go_h200_sxm.sh
```

That single command:

- preflights SSH + ≥2 GPUs
- fast-bootstraps the pod (reuses template torch)
- CUDA smoke-tests a real Conv2d
- syncs the repo and uploads saved checkpoints
- launches GPU round-1, H200 round-2 followon, CPU elite, hotzone GEBCO
- babysits / heals until every gate in `pod_pipeline_green.sh` is green
- pulls models + validation + logs locally, then exits 0

Optional overrides:

```bash
GPU_MAX_HOURS=16 REQUIRE_H200=1 bash scripts/pod/go_h200_sxm.sh
RESUME_MODELS=/path/to/artifacts/.../models bash scripts/pod/go_h200_sxm.sh
```

Status / final pull (if you need them separately):

```bash
bash scripts/pod/pod_pipeline_green.sh
bash scripts/pod/pull_h200_shutdown.sh
```

## Phase 2 baseline

```bash
bash scripts/pod/pod_hybrid_phase2.sh
```
