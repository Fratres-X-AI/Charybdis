#!/usr/bin/env bash
set -euo pipefail
cd /workspace/Charybdis
sed -i 's/\r$//' scripts/pod/pod_max_gpu_lane.sh
python3 - <<'PY'
from pathlib import Path
p = Path("scripts/pod/pod_max_gpu_lane.sh")
for i, line in enumerate(p.read_text().splitlines(), 1):
    if i >= 100:
        print(f"{i}: {line}")
PY
