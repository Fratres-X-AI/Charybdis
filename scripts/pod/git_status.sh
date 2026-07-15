#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
git status
echo '---DIFF---'
git diff
echo '---STAGED---'
git diff --staged
echo '---LOG---'
git log -5 --oneline
