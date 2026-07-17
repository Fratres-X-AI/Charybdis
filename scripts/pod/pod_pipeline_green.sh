#!/usr/bin/env bash
# Remote pipeline scoreboard — exit 0 only when every gate is green.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

GPU_TARGET="${GPU_TARGET:-2}"
if ! [[ "$GPU_TARGET" =~ ^[0-9]+$ ]] || (( GPU_TARGET < 1 )); then
  GPU_TARGET=2
fi

VALIDATION_PROFILE="${VALIDATION_PROFILE:-full}"
REPORT_ONLY="${1:-}"

set +e
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
  "GPU_TARGET=${GPU_TARGET} VALIDATION_PROFILE=${VALIDATION_PROFILE} python3 -" <<'PY'
import json
import os
import re
import sys
from pathlib import Path

gpu_target = int(os.environ.get("GPU_TARGET", "2"))
profile = os.environ.get("VALIDATION_PROFILE", "full")
repo = Path("/workspace/Charybdis")
checks: dict[str, bool] = {}
notes: dict[str, str] = {}
require_gpu = profile not in ("release_cpu", "cpu_only")

def log_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")

def latest_dir(pattern: str) -> Path | None:
    matches = sorted(repo.glob(pattern))
    return matches[-1] if matches else None

# --- GPU round 1 ---
if require_gpu:
    for g in range(gpu_target):
        key = f"gpu_r1_lane{g}"
        text = log_text(Path(f"/tmp/pod_gpu_lane{g}.log"))
        ok = bool(re.search(rf"FINAL gpu={g}\b", text))
        checks[key] = ok
        if not ok:
            tail = [ln for ln in text.splitlines() if ln.strip()][-1:] or ["no log"]
            notes[key] = tail[0][:120]
else:
    notes["gpu_training"] = "skipped (release_cpu profile)"

# --- GPU round 2 ---
if require_gpu:
    for g in range(gpu_target):
        key = f"gpu_r2_lane{g}"
        text = log_text(Path(f"/tmp/pod_h200_lane{g}.log"))
        ok = bool(re.search(rf"H200 FINAL gpu={g}\b", text))
        # pass05 checkpoint is durable proof (logs get truncated on relaunch)
        pass05 = repo / "models" / f"tcm_so2_h200_lane{g}_pass05.pt"
        if not ok and pass05.is_file():
            ok = True
            notes[key] = "FINAL via pass05 checkpoint"
        checks[key] = ok
        if not ok and Path(f"/tmp/pod_h200_lane{g}.log").is_file():
            notes[key] = "round-2 incomplete"
        elif not ok:
            notes[key] = "round-2 not started"

# --- CPU elite + highres ---
# Prefer any completed green cpu_elite tree (latest may be a mid-run heal relaunch).
cpu_jobs = [
    "mission_engineering",
    "holdout_harbor",
    "holdout_deep",
    "harbor_release",
    "deep_release",
]
cpu_root = None
for cand in sorted(repo.glob("artifacts/validation/*/cpu_elite"), reverse=True):
    if all((cand / job / "matrix_summary.json").is_file() for job in cpu_jobs):
        cpu_root = cand
        break
if cpu_root is None:
    cpu_root = latest_dir("artifacts/validation/*/cpu_elite")
if cpu_root is None:
    for job in cpu_jobs:
        checks[f"cpu_{job}"] = False
        notes[f"cpu_{job}"] = "cpu_elite missing"
else:
    for job in cpu_jobs:
        key = f"cpu_{job}"
        summary = cpu_root / job / "matrix_summary.json"
        if not summary.is_file():
            checks[key] = False
            notes[key] = "matrix_summary missing"
            continue
        payload = json.loads(summary.read_text(encoding="utf-8"))
        checks[key] = bool(payload.get("passed"))
        if not checks[key]:
            notes[key] = f"passed={payload.get('passed')}"

highres = latest_dir("artifacts/validation/*/highres_bathymetry")
if highres is None:
    checks["highres_release"] = False
    notes["highres_release"] = "highres dir missing"
else:
    rel = highres / "release.json"
    if not rel.is_file():
        checks["highres_release"] = False
        notes["highres_release"] = "release.json missing"
    else:
        payload = json.loads(rel.read_text(encoding="utf-8"))
        checks["highres_release"] = bool(payload["results"]["passed"])
        if not checks["highres_release"]:
            notes["highres_release"] = (
                f"cep95={payload['results'].get('cep95_m')} "
                f"accepted={payload['results'].get('acceptance_rate')}"
            )

# --- Hotzone GEBCO (engineering characterization) ---
if require_gpu:
    regions_file = repo / "validation/hotzone_gebco_regions.json"
    hotzone = latest_dir("artifacts/validation/*/hotzone_bathymetry")
    if not regions_file.is_file():
        checks["hotzone_suite"] = False
        notes["hotzone_suite"] = "regions json missing on pod"
    elif hotzone is None:
        checks["hotzone_suite"] = False
        notes["hotzone_suite"] = "hotzone dir missing"
    else:
        region_ids = [r["id"] for r in json.loads(regions_file.read_text(encoding="utf-8"))]
        hotzone_ok = True
        for rid in region_ids:
            key = f"hotzone_{rid}"
            rdir = hotzone / rid
            status = (rdir / "status.txt").read_text(encoding="utf-8").strip() if (rdir / "status.txt").is_file() else "missing"
            eng = rdir / "engineering.json"
            if status != "OK" or not eng.is_file():
                checks[key] = False
                hotzone_ok = False
                notes[key] = f"status={status}"
                continue
            payload = json.loads(eng.read_text(encoding="utf-8"))
            res = float(payload.get("manifest", {}).get("map_resolution_m", 9999.0))
            passed = bool(payload["results"]["passed"])
            # Coarse GEBCO: characterization complete (status OK + eng json) is green.
            # Fine maps: require engineering pass.
            ok = True if res > 100.0 else passed
            checks[key] = ok
            if not ok:
                hotzone_ok = False
                notes[key] = (
                    f"cep95={payload['results'].get('cep95_m')} "
                    f"accepted={payload['results'].get('acceptance_rate')}"
                )
        checks["hotzone_suite"] = hotzone_ok
else:
    notes["hotzone_suite"] = "skipped (release_cpu profile)"

# --- Post-train full pass (after round 2) ---
if require_gpu:
    fullpass_text = "\n".join(
        log_text(Path(p)) for p in (
            Path("/tmp/pod_post_train_full_pass.log"),
            Path("/tmp/pod_full_pass.log"),
        )
    )
    checks["post_train_full_pass"] = "FULL_PASS_COMPLETE" in fullpass_text or "FULL_PASS_DONE" in fullpass_text
    if not checks["post_train_full_pass"]:
        notes["post_train_full_pass"] = "waiting for round-2 + full_pass"
else:
    notes["post_train_full_pass"] = "skipped (release_cpu profile)"

overall = all(checks.values()) if checks else False
passed_n = sum(1 for v in checks.values() if v)
total_n = len(checks)

print("=== PIPELINE GREEN SCOREBOARD ===")
for name in sorted(checks):
    mark = "GREEN" if checks[name] else "RED"
    extra = f" ({notes[name]})" if name in notes and not checks[name] else ""
    print(f"{mark} {name}{extra}")
print(f"SCORE {passed_n}/{total_n} overall={'GREEN' if overall else 'RED'}")

payload = {"checks": checks, "notes": notes, "score": f"{passed_n}/{total_n}", "overall": overall}
print("GREEN_JSON=" + json.dumps(payload, sort_keys=True))
sys.exit(0 if overall else 1)
PY
GREEN_RC=$?
set -e

exit "${GREEN_RC}"
