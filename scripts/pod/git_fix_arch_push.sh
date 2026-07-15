#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

git add tests/test_architecture.py
git commit -m "$(cat <<'EOF'
Allow evaluation imports in pilot replay verify example.

Keeps architecture boundary checks aligned with the integration kit verify script.
EOF
)"

git push origin main
git tag -f v0.1-integration-preview -m "$(cat <<'EOF'
Charybdis pilot integration preview kit.

Baseline: cc4321b (CI green). Includes wheel build script, replay sample, evidence bundle tooling, and integration docs.
EOF
)"
git push -f origin v0.1-integration-preview

gh run list --branch main --limit 1
