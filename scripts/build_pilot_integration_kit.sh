#!/usr/bin/env bash
# Build dist/charybdis_pilot_integration_kit_v0.1-integration-preview.zip
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TAG="v0.1-integration-preview"
BASE_SHA="${PILOT_BASE_SHA:-cc4321b}"
CI_URL="${PILOT_CI_URL:-https://github.com/Fratres-X-AI/Charybdis/actions/runs/29365217553}"
STAGING="$ROOT/dist/pilot_kit_staging"
OUT_ZIP="$ROOT/dist/charybdis_pilot_integration_kit_${TAG}.zip"

INTEGRATION_SRC="${PILOT_INTEGRATION_SRC:-artifacts/pod_integration_pull_20260714T193353Z}"
HIGHRES_SRC="${PILOT_HIGHRES_SRC:-artifacts/pod_highres_bathy_pull_20260714T200715Z}"
RELEASE_SRC="${PILOT_RELEASE_SRC:-artifacts/pod_l40s_pull_20260714T180953Z/validation/20260714T180650Z-51cc3dd-13022/release_grade}"

log() { echo "[pilot-kit] $*"; }

rm -rf "$STAGING"
mkdir -p "$STAGING"/{wheel,docs,samples,examples,evidence/integration_grade,evidence/release_grade,evidence/highres_bathymetry}

log "build wheel"
python -m pip install -q build
python -m build --wheel --outdir "$STAGING/wheel"

log "pinned requirements"
cp requirements/ci.txt "$STAGING/requirements-ci.txt"

log "docs"
for doc in STABLE_API.md PILOT_EXEC_SUMMARY.md PILOT_INTEGRATION_KIT.md INTEGRATION_HANDOFF.md KNOWN_LIMITS.md; do
  cp "docs/$doc" "$STAGING/docs/"
done

log "sample replay"
python scripts/generate_mission_replay_sample.py \
  --output "$STAGING/samples/mission_replay.json" \
  --steps 120 \
  --seed 23390824

cp examples/verify_pilot_replay.py "$STAGING/examples/"

log "evidence integration_grade"
if [[ -d "$INTEGRATION_SRC/engineering" ]]; then
  cp "$INTEGRATION_SRC/engineering/matrix_summary.json" "$STAGING/evidence/integration_grade/harbor_engineering.json"
  cp "$INTEGRATION_SRC/engineering/REPORT.md" "$STAGING/evidence/integration_grade/harbor_engineering.md" 2>/dev/null || true
fi
if [[ -d "$INTEGRATION_SRC/deep_engineering" ]]; then
  cp "$INTEGRATION_SRC/deep_engineering/matrix_summary.json" "$STAGING/evidence/integration_grade/deep_engineering.json"
  cp "$INTEGRATION_SRC/deep_engineering/REPORT.md" "$STAGING/evidence/integration_grade/deep_engineering.md" 2>/dev/null || true
fi

log "evidence release_grade"
if [[ -d "$RELEASE_SRC/harbor_release" ]]; then
  cp "$RELEASE_SRC/harbor_release/matrix_summary.json" "$STAGING/evidence/release_grade/harbor_release.json"
  cp "$RELEASE_SRC/harbor_release/REPORT.md" "$STAGING/evidence/release_grade/harbor_release.md" 2>/dev/null || true
fi
if [[ -d "$RELEASE_SRC/deep_release" ]]; then
  cp "$RELEASE_SRC/deep_release/matrix_summary.json" "$STAGING/evidence/release_grade/deep_release.json"
  cp "$RELEASE_SRC/deep_release/REPORT.md" "$STAGING/evidence/release_grade/deep_release.md" 2>/dev/null || true
fi

log "evidence highres_bathymetry"
if [[ -d "$HIGHRES_SRC" ]]; then
  cp "$HIGHRES_SRC/release.json" "$STAGING/evidence/highres_bathymetry/"
  cp "$HIGHRES_SRC/release.md" "$STAGING/evidence/highres_bathymetry/" 2>/dev/null || true
  cp "$HIGHRES_SRC/engineering.json" "$STAGING/evidence/highres_bathymetry/" 2>/dev/null || true
  cp "$HIGHRES_SRC/noaa_monterey_bay_p080.json" "$STAGING/evidence/highres_bathymetry/tile_metadata.json" 2>/dev/null || true
  cp "$HIGHRES_SRC/README.md" "$STAGING/evidence/highres_bathymetry/" 2>/dev/null || true
fi

cat >"$STAGING/evidence/CI.txt" <<EOF
Charybdis pilot integration kit — CI evidence
============================================
Baseline SHA: ${BASE_SHA}
Tag: ${TAG}
CI run (PASS): ${CI_URL}
Built: $(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

HEAD_SHA="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
export PILOT_KIT_STAGING="$STAGING"
export PILOT_KIT_TAG="$TAG"
export PILOT_KIT_BASE_SHA="$BASE_SHA"
export PILOT_KIT_BUILD_SHA="$HEAD_SHA"
export PILOT_KIT_CI_URL="$CI_URL"
python - <<'PY'
import hashlib
import json
import os
from pathlib import Path

staging = Path(os.environ["PILOT_KIT_STAGING"])
files = []
for path in sorted(staging.rglob("*")):
    if path.is_file():
        rel = path.relative_to(staging).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files.append({"path": rel, "sha256": digest, "bytes": path.stat().st_size})

manifest = {
    "kit": "charybdis-pilot-integration-kit",
    "tag": os.environ["PILOT_KIT_TAG"],
    "baseline_sha": os.environ["PILOT_KIT_BASE_SHA"],
    "build_sha": os.environ["PILOT_KIT_BUILD_SHA"],
    "ci_url": os.environ["PILOT_KIT_CI_URL"],
    "files": files,
}
(staging / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(f"manifest files={len(files)}")
PY

log "verify replay in staging"
(
  cd "$STAGING"
  PYTHONPATH="$ROOT" python examples/verify_pilot_replay.py --replay samples/mission_replay.json
)

mkdir -p "$ROOT/dist"
rm -f "$OUT_ZIP"
export PILOT_KIT_OUT_ZIP="$OUT_ZIP"
(
  cd "$STAGING"
  python - <<'PY'
import os
import zipfile
from pathlib import Path

staging = Path(".")
out = Path(os.environ["PILOT_KIT_OUT_ZIP"])
with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(staging.rglob("*")):
        if path.is_file():
            archive.write(path, path.as_posix())
print(f"zip bytes={out.stat().st_size}")
PY
)

du -sh "$OUT_ZIP"
log "PILOT_KIT_COMPLETE $OUT_ZIP"
