# Remote validation helpers

Scripts for ephemeral cloud GPU instances. Not part of the installable package.
Run from Git Bash on the mission-control host.

Full guide: [`docs/REMOTE_VALIDATION.md`](../../docs/REMOTE_VALIDATION.md)

## Release verification (no GPU)

```bash
bash scripts/pod/verify_release_cpu.sh
```

## Optional GPU retraining

```bash
# Edit scripts/pod/pod_env.sh first
bash scripts/pod/launch_gpu_train.sh
bash scripts/pod/run_remote_validation.sh
bash scripts/pod/go_monitor_pipeline.sh
bash scripts/pod/pod_pipeline_green.sh
```

## Phase 2 baseline

```bash
bash scripts/pod/pod_hybrid_phase2.sh
```

Internal script names under `scripts/pod/` are operational only and are not
referenced in release documentation.
