#!/usr/bin/env bash
# 10-pass escalating SO(2) hard training for A100. Run ON POD only.
set -euo pipefail
cd /workspace/Charybdis
source .venv/bin/activate
export PYTHONPATH=. PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1

LOG=ten_pass.log
MODEL=models/tcm_so2.pt
mkdir -p models
cp -f charybdis/models/tcm_so2.pt "$MODEL" 2>/dev/null || true

exec >> "$LOG" 2>&1
echo "=== 10-PASS LADDER start $(date -u) ==="

python -u <<'PY'
import shutil
import numpy as np
import torch
from charybdis.config import SimConfig
from charybdis.terrain import Terrain
from charybdis.experimental.nn_matcher import train, eval_hard, build_model

PASSES = [
    # ep, samples, batch, terrains, lr, seed
    (12,  60_000,  2048, 12, 1.0e-4, 101),
    (15,  80_000,  2048, 14, 8.0e-5, 202),
    (18, 100_000,  3072, 16, 7.0e-5, 303),
    (20, 120_000,  3072, 18, 6.0e-5, 404),
    (22, 140_000,  4096, 20, 5.5e-5, 505),
    (25, 160_000,  4096, 22, 5.0e-5, 606),
    (28, 180_000,  4096, 24, 4.0e-5, 707),
    (30, 200_000,  4096, 26, 3.5e-5, 808),
    (32, 220_000,  4096, 28, 2.5e-5, 909),
    (35, 250_000,  4096, 32, 2.0e-5, 1010),
]

print("gpu", torch.cuda.get_device_name(0))
best_after = 1e9
best_pass = 0

for i, (ep, ns, bs, nt, lr, seed) in enumerate(PASSES, 1):
    print(f"\n{'='*60}\nPASS {i}/10: {ep}ep x {ns} @{bs} terr={nt} lr={lr:.1e} hard\n{'='*60}")
    train(epochs=ep, n_samples=ns, batch=bs, seed=seed, device="cuda",
          n_terrains=nt, resume="models/tcm_so2.pt", lr=lr, hard=True,
          model_path="models/tcm_so2.pt")
    shutil.copy("models/tcm_so2.pt", f"models/tcm_so2_pass{i:02d}.pt")

    m = build_model()
    m.load_state_dict(torch.load("models/tcm_so2.pt", map_location="cuda", weights_only=True))
    m.cuda().eval()
    terrains = [Terrain.synthetic(SimConfig(seed=seed + j)) for j in range(nt)]
    rng = np.random.default_rng(seed + 9999)
    hm = eval_hard(m, terrains, 350.0, "cuda", rng, n=8192, infer_batch=1024)
    print(f"PASS {i} EVAL after_mean={hm['after_mean']:.1f}m p50={hm['after_p50']:.0f} "
          f"p95={hm['after_p95']:.0f} imp={hm['improve_pct']:.0f}%")
    if hm["after_mean"] < best_after:
        best_after = hm["after_mean"]
        best_pass = i
        shutil.copy("models/tcm_so2.pt", "models/tcm_so2_best.pt")
        print(f"  -> new best checkpoint (pass {i})")

print(f"\n=== FINAL EVAL (best pass {best_pass}, after_mean={best_after:.1f}m) n=16384 ===")
m = build_model()
m.load_state_dict(torch.load("models/tcm_so2_best.pt", map_location="cuda", weights_only=True))
m.cuda().eval()
terrains = [Terrain.synthetic(SimConfig(seed=i)) for i in range(32)]
rng = np.random.default_rng(42)
final = eval_hard(m, terrains, 350.0, "cuda", rng, n=16384, infer_batch=1024)
print("FINAL", final)
shutil.copy("models/tcm_so2_best.pt", "models/tcm_so2.pt")
shutil.copy("models/tcm_so2.pt", "charybdis/models/tcm_so2.pt")
print("saved models/tcm_so2.pt + charybdis/models/tcm_so2.pt")
PY

echo "=== 10-PASS LADDER done $(date -u) ==="
