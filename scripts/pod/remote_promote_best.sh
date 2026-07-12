#!/usr/bin/env bash
set -euo pipefail
cd /workspace/Charybdis
python3 - <<'PY'
from pathlib import Path
import re
import shutil

root = Path("/workspace/Charybdis/models")
candidates = []
for gpu, log in [(0, Path("/tmp/pod_gpu_lane0.log")), (1, Path("/tmp/pod_gpu_lane1.log"))]:
    text = log.read_text(errors="ignore") if log.exists() else ""
    matches = re.findall(r"FINAL gpu=\d lane=\w+ best_pass=(\d+) \{[^}]*'after_mean': ([0-9.]+)", text)
    if matches:
        _, mean = matches[-1]
        model = root / f"tcm_so2_best_lane{gpu}.pt"
        if model.exists():
            candidates.append((float(mean), gpu, model))

if not candidates:
    raise SystemExit("no final candidates")

mean, gpu, model = min(candidates)
shutil.copy(model, root / "tcm_so2.pt")
shutil.copy(model, root / "tcm_so2_best.pt")
print(f"PROMOTED gpu={gpu} after_mean={mean:.3f} {model.name}")
PY
ls -lh models/tcm_so2.pt models/tcm_so2_best.pt models/tcm_so2_best_lane*.pt
