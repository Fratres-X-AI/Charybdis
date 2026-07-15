#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
RUN_ID="${1:-29364718304}"
gh run view "$RUN_ID" --log-failed
