#!/usr/bin/env bash
# Poll pod every 60s (bash only — do not run via PowerShell).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
for i in $(seq 1 120); do
  echo "--- poll $i ---"
  bash "$SCRIPT_DIR/poll_dual.sh"
  sleep 60
done
