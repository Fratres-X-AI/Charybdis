#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ART="$ROOT/artifacts"

echo "=== LOCAL PULL DIRS ==="
du -sh "$ART"/pod_h200_final_* 2>/dev/null | sort -h

echo "=== BEST MODEL SET (191348Z if present) ==="
for d in "$ART"/pod_h200_final_*; do
  m0="$d/models/tcm_so2_h200_lane0_pass05.pt"
  m1="$d/models/tcm_so2_h200_lane1_pass05.pt"
  act="$d/models/tcm_so2.pt"
  if [[ -f "$m0" && -f "$m1" && -f "$act" ]]; then
    echo "OK models: $d"
    ls -lh "$act" "$d/models/tcm_so2_best.pt" "$m0" "$m1" 2>/dev/null || true
  fi
done

echo "=== FULL_PASS LOCALLY ==="
find "$ART"/pod_h200_final_*/validation -name 'FULL_PASS_*' 2>/dev/null | head -20

echo "=== ACTIVE SCP/PULL ==="
ps -ef 2>/dev/null | grep -E 'scp|pull_h200|_fast_critical' | grep -v grep | wc -l | xargs -I{} echo "pull_related_procs={}"
ps -ef 2>/dev/null | grep -E 'scp.*validation|pull_h200|_fast_critical' | grep -v grep | head -15 || true
