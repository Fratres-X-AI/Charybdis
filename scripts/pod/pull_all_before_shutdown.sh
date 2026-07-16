#!/usr/bin/env bash
# Pull all validation artifacts + logs from active pod before shutdown.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
DEST="$LOCAL_ROOT/artifacts/pod_final_pull_${STAMP}"
mkdir -p "$DEST/validation" "$DEST/logs"

echo "=== stop background loops (best-effort) ==="
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
  'pkill -f pod_cpu_loop || true; pkill -f hybrid_validate || true; pkill -f real_bathymetry_validate || true; sleep 1; pgrep -c -f hybrid_validate 2>/dev/null || echo 0' || true

echo "=== remote validation dirs ==="
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
  'ls -1d /workspace/Charybdis/artifacts/validation/* 2>/dev/null | tail -30'

echo "=== pull full validation tree ==="
scp -P "$POD_PORT" -i "$POD_KEY" -r \
  "$POD_HOST:/workspace/Charybdis/artifacts/validation" \
  "$DEST/"

echo "=== pull pod logs ==="
for f in \
  pod_metric_sprint_stdout.log pod_metric_sprint.log \
  pod_max_out_stdout.log pod_max_out.log \
  pod_max_harbor_rel.log pod_max_deep_rel.log \
  pod_max_harbor_worst.log pod_max_deep_worst.log pod_max_highres.log \
  pod_mission_matrix.log \
  pod_cpu_loop.log pod_cpu_loop_stdout.log \
  pod_integration_grade.log pod_integration_grade_stdout.log \
  pod_highres_bathy.log pod_release_grade_stdout.log \
  pod_validation_day.log pod_validation_day_stdout.log \
  pod_full_pass.log pod_full_pass_stdout.log \
  pod_holdout_deep_rerun.log pod_holdout_deep_rerun_stdout.log \
  pod_int_harbor.log pod_int_deep.log pod_rel_harbor.log pod_rel_deep.log \
  pod_worst_harbor.log pod_worst_deep.log; do
  scp -P "$POD_PORT" -i "$POD_KEY" \
    "$POD_HOST:/tmp/$f" "$DEST/logs/" 2>/dev/null || true
done

echo "=== git state ==="
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
  'cd /workspace/Charybdis && echo pod='"${POD_NAME}"' && git rev-parse HEAD && git log -1 --oneline' \
  > "$DEST/git_state.txt" 2>&1 || true

python3 - <<PY || true
import json
from pathlib import Path

dest = Path(r"$DEST")
lines = ["# Pod final pull", "", f"- Pulled: ${STAMP} UTC", f"- Pod: ${POD_NAME}", "", "## Summaries", ""]
val = dest / "validation"
if val.is_dir():
    for summary in sorted(val.rglob("matrix_summary.json"), key=lambda p: p.stat().st_mtime)[-12:]:
        try:
            data = json.loads(summary.read_text())
            lines.append(f"- \`{summary.parent.relative_to(dest)}\`: passed={data.get('passed')} tier={data.get('tier')}")
        except Exception:
            pass
    for summary in sorted(val.rglob("release.json"), key=lambda p: p.stat().st_mtime)[-3:]:
        try:
            data = json.loads(summary.read_text())
            r = data["results"]
            lines.append(f"- \`{summary.parent.relative_to(dest)}/release.json\`: pass={r['passed']} cep95={r['cep95_m']:.3f} accepted={r['acceptance_rate']:.3f}")
        except Exception:
            pass
(dest / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

echo "PULL_COMPLETE dest=$DEST"
du -sh "$DEST" 2>/dev/null || true
find "$DEST" -name 'matrix_summary.json' 2>/dev/null | wc -l | xargs -I{} echo "matrix_summaries={}"
