# Agent Operating Rules

These instructions apply to every AI/code agent working in this repository.

## RunPod / Remote GPU Rules

- Use **Git Bash only** for RunPod SSH/SCP/remote execution. Do not run pod operations through PowerShell.
- Know the two RunPod SSH modes:
  - Basic SSH uses `ssh.runpod.io`; it is proxied and does **not** support SCP/SFTP.
  - SSH over exposed TCP uses `root@<public-ip> -p <external-port>`; it supports SCP/SFTP and is required for artifact pulls.
- Always use direct TCP SSH for repo sync, SCP/SFTP, artifact transfer, and Cursor Remote-SSH.
- Verify the pod exposes TCP `22` and the Connect tab shows a Direct TCP mapping (`<ip>:<external-port> -> :22`). If direct TCP SSH is unavailable, do not run workflows that need file transfer.
- Confirm pod access and GPU inventory before work:

```bash
source scripts/pod/pod_env.sh
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" 'echo OK; nvidia-smi -L'
```

- Confirm the GPU can execute the installed PyTorch build with a real CUDA operation before launching training. `torch.cuda.is_available()` alone is not enough.
- Blackwell GPUs (RTX 50xx, RTX PRO 4500/6000, B200) require a compatible CUDA 12.8+ PyTorch build or RunPod's PyTorch 2.8 + CUDA 12.8 image. If CUDA fails with `no kernel image is available for execution on the device`, fix PyTorch before attempting training again.
- Cost policy: release CPU validation requires no GPU; optional retraining should use the cheapest compatible GPU with enough VRAM. Do not recommend H200 unless the user explicitly asks or the workload requires 141GB VRAM.
- Never tell the user a pod is safe to stop until:
  - all in-scope gates are green;
  - logs show final completion, not just process launch;
  - artifacts have been pulled locally; and
  - the final local artifact path is reported.
- If the user asks for status, report actual state: running processes, GPU utilization, latest lane log, pass/fail gates, and blockers.
- Do not spend or recommend expensive GPUs unless they are required for the stated gate. Prefer release CPU validation or cheaper compatible GPUs when sufficient.

## Communication Rules

- Be direct when something failed. Do not frame partial work as complete.
- Separate "completed", "running", "blocked", and "next action".
- Do not hide setup time, compatibility failures, or missing artifacts behind optimistic language.
