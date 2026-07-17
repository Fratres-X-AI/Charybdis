#!/usr/bin/env bash
# Fast pod bootstrap for RunPod PyTorch templates (H200 SXM).
# Uses system-site-packages so the template torch is reused; installs only missing deps.
set -euo pipefail

REPO=/workspace/Charybdis
cd "$REPO"
export PYTHONPATH=.
export DEBIAN_FRONTEND=noninteractive

PY=python3
command -v python >/dev/null 2>&1 && PY=python

if [[ ! -d .venv ]]; then
  echo "[bootstrap] creating venv --system-site-packages"
  "$PY" -m venv --system-site-packages .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install -q -U pip setuptools wheel
# Minimal train/validate stack — do not reinstall torch unless missing
python - <<'PY'
import importlib.util
import subprocess
import sys

need = []
for pkg in ("numpy", "scipy"):
    if importlib.util.find_spec(pkg) is None:
        need.append(pkg)
if need:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *need])

try:
    import torch
    assert torch.cuda.is_available()
    print("torch_ok", torch.__version__, torch.cuda.get_device_name(0))
except Exception as exc:
    print("torch_missing_or_broken", exc)
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-q",
            "torch",
            "--index-url",
            "https://download.pytorch.org/whl/cu126",
        ]
    )
PY

# Editable install without pulling a second torch if possible
python -m pip install -q -e . --no-deps 2>/dev/null || python -m pip install -q -e . || true

python - <<'PY'
import torch
import torch.nn as nn
assert torch.cuda.device_count() >= 1
x = torch.randn(2, 8, 16, 16, device="cuda")
y = nn.Conv2d(8, 8, 3, padding=1).cuda()(x)
print("BOOTSTRAP_OK", torch.cuda.device_count(), [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())], tuple(y.shape))
PY
