# Remote GPU validation

Ephemeral cloud GPU workflows for matcher retraining and extended validation.
Operational scripts live under `scripts/pod/` and are not part of the installable
package. Use **Git Bash** on the mission-control host.

## Prerequisites

- SSH access to an active GPU instance through **SSH over exposed TCP**
- Repository checkout with baseline weights at `models/tcm_so2.pt`
- Configure [`scripts/pod/pod_env.sh`](../scripts/pod/pod_env.sh):

```bash
export POD_NAME=<instance_name>
export POD_HOST=root@<ip>
export POD_PORT=<ssh_port>
export POD_KEY="/c/Users/<you>/.ssh/id_ed25519"
```

## RunPod SSH / TCP rules

RunPod exposes two SSH modes:

| Mode | Example | SCP/SFTP | Use for |
|------|---------|----------|---------|
| Basic SSH proxy | `ssh <pod-id>@ssh.runpod.io -i ~/.ssh/id_ed25519` | No | Emergency shell only |
| SSH over exposed TCP | `ssh root@<public-ip> -p <external-port> -i ~/.ssh/id_ed25519` | Yes | All repo sync, artifact pull, Cursor Remote-SSH |

Operational rules:

- Use **Git Bash only** for all pod commands from Windows.
- Do not use the proxied `ssh.runpod.io` command for workflows that need SCP/SFTP.
- The pod must expose TCP port `22`, run `sshd`, and show a Direct TCP mapping such as `<ip>:<external-port> -> :22`.
- Public IPs and external port mappings can change when a pod resets, especially on Community Cloud. Re-check the Connect tab and update `pod_env.sh` after every restart or migration.
- HTTP proxy ports are for web services like Jupyter (`8888/http`), not SSH/SCP.
- Direct TCP is for SSH and other raw TCP protocols. RunPod does not support UDP pod exposure.

## GPU / PyTorch compatibility

Before training, verify both inventory and a real CUDA operation:

```bash
python - <<'PY'
import torch
import torch.nn as nn
print(torch.__version__, torch.version.cuda, torch.cuda.device_count())
for i in range(torch.cuda.device_count()):
    print(i, torch.cuda.get_device_name(i), torch.cuda.get_device_capability(i))
    x = torch.randn(8, 1, 32, 32, device=f"cuda:{i}")
    y = nn.Conv2d(1, 4, 3).to(f"cuda:{i}")(x)
    torch.cuda.synchronize(i)
    print("conv_ok", i, tuple(y.shape))
PY
```

`torch.cuda.is_available()` is not enough. If this test fails, do not launch
training.

Blackwell GPUs (`RTX 50xx`, `RTX PRO 4500/6000`, `B200`) need a compatible
CUDA 12.8+ PyTorch build. Prefer RunPod's official `PyTorch 2.8 + CUDA 12.8`
template for Blackwell pods. The failure signature for an incompatible build is:

```text
RuntimeError: CUDA error: no kernel image is available for execution on the device
```

## GPU selection policy

Use the cheapest GPU that satisfies the gate:

| Goal | Recommended path |
|------|------------------|
| Release CPU validation | No GPU required |
| Small CUDA smoke / script debugging | Cheap 24GB GPU if compatible |
| Optional SO(2) retrain | L40S, RTX 6000 Ada, or A100 with adjusted batch |
| High-VRAM experiments | A100 80GB / H100 only if needed |
| H200 | Only if explicitly requested or >100GB VRAM is truly required |
| Blackwell cards | Use PyTorch 2.8 + CUDA 12.8 template before any training |

## Validation profiles

### Release CPU (no additional GPU cost)

Synthetic and integration-grade CPU gates **already passed** on the July 2026
pull (`artifacts/pod_h200_final_20260717T143729Z/`):

- Mission engineering 6/6
- Holdout harbor + deep 7/7
- Harbor + deep release 7/7
- NOAA Monterey highres **PASS** (CEP95 9.78 m)

To verify locally without renting GPUs:

```bash
python -m pytest tests/test_architecture.py
python -m pytest -m "not console" --cov=charybdis --cov-fail-under=80
python examples/verify_pilot_replay.py
```

Use `VALIDATION_PROFILE=release_cpu` when checking remote completion status
(GPU training gates skipped):

```bash
VALIDATION_PROFILE=release_cpu bash scripts/pod/pod_pipeline_green.sh
```

### Full GPU retrain (optional)

For NN SO(2) matcher retraining, any CUDA instance with **≥1 GPU** works.
Dual-GPU runs train two lanes in parallel; single-GPU runs sequentially.
**A100 80GB** or **L40S** is sufficient at lower batch sizes — H200 is not required.

```text
launch_gpu_train.sh     → sync + round-1 training lanes
kick_saturate_h200.sh     → parallel CPU validation + follow-on watcher
go_monitor_pipeline.sh  → poll until completion gates pass, then pull
```

## Completion gates

[`scripts/pod/pod_pipeline_green.sh`](../scripts/pod/pod_pipeline_green.sh)
reports gate status. Default profile requires GPU round 1/2 FINAL, CPU matrices,
highres NOAA, hotzone engineering, and post-train full pass.

Check status:

```bash
bash scripts/pod/pod_pipeline_green.sh
```

Monitor until all gates pass:

```bash
bash scripts/pod/launch_gpu_train.sh
bash scripts/pod/kick_saturate_h200.sh
bash scripts/pod/go_monitor_pipeline.sh
```

Incremental monitoring (5 min pulls):

```bash
bash scripts/pod/monitor_away.sh
```

Final artifact pull before instance termination:

```bash
bash scripts/pod/pull_h200_shutdown.sh
```

## Phase 2 baseline

Synthetic + GEBCO characterization without NN retraining:

```bash
cd /workspace/Charybdis
bash scripts/pod/pod_hybrid_phase2.sh
```

See [`VALIDATION.md`](VALIDATION.md) for tier definitions and worker limits (max 31).

## Limitations

- Completion gates are **software validation**, not sea trial or certification.
- Coarse GEBCO regional tiles are characterization only (~450 m).
- Promote retrained weights only after reviewing FINAL metrics and full-pass logs.
