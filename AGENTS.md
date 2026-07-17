# Agent Operating Rules

These instructions apply to every AI/code agent working in this repository.

## RunPod / Remote GPU Rules

- Use **Git Bash only** for RunPod SSH/SCP/remote execution. Do not run pod operations through PowerShell.
- Always use direct TCP SSH for artifact transfer.
- Confirm pod access and GPU inventory before work:

```bash
source scripts/pod/pod_env.sh
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" 'echo OK; nvidia-smi -L'
```

- Confirm the GPU can execute the installed PyTorch build with a real CUDA operation before launching training. `torch.cuda.is_available()` alone is not enough.
- Blackwell GPUs require a PyTorch build with compatible kernels. If CUDA fails with `no kernel image is available for execution on the device`, fix PyTorch before attempting training again.
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
