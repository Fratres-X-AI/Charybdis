#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
git add tests/test_real_bathymetry_contracts.py
git commit -m "$(cat <<'EOF'
Fix import order in real-bathymetry contract tests for ruff.

EOF
)"
git push
gh run list --branch main --limit 3
