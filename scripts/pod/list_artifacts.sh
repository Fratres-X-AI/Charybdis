#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ls -la "$ROOT/artifacts" 2>/dev/null | head -25 || echo "no artifacts dir"
