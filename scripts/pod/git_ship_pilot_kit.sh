#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

git add \
  docs/PILOT_EXEC_SUMMARY.md \
  docs/PILOT_INTEGRATION_KIT.md \
  examples/verify_pilot_replay.py \
  scripts/build_pilot_integration_kit.sh \
  scripts/generate_mission_replay_sample.py \
  pilot_integration_kit/samples/mission_replay.json \
  pilot_integration_kit/samples/mission_replay.meta.json

git commit -m "$(cat <<'EOF'
Add pilot integration kit for v0.1-integration-preview.

Ship build tooling, docs, deterministic replay sample, and hardware-free verify script so AUV integrators can evaluate without the full repo.
EOF
)"

git tag -a v0.1-integration-preview -m "$(cat <<'EOF'
Charybdis pilot integration preview kit.

Baseline: cc4321b (CI green). Includes wheel build script, replay sample, evidence bundle tooling, and integration docs.
EOF
)"

git push origin main
git push origin v0.1-integration-preview

git status
git log -1 --oneline
git tag -l 'v0.1-integration-preview' -n1
