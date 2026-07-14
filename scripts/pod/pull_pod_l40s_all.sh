#!/usr/bin/env bash
# Pull all validation artifacts from active pod before shutdown.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/pod_env.sh"

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
DEST="$LOCAL_ROOT/artifacts/pod_l40s_pull_${STAMP}"
mkdir -p "$DEST"

echo "=== list remote validation dirs ==="
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
  'ls -1d /workspace/Charybdis/artifacts/validation/20260714T* 2>/dev/null | sort'

echo "=== pull validation tree (20260714) ==="
scp -P "$POD_PORT" -i "$POD_KEY" -r \
  "$POD_HOST:/workspace/Charybdis/artifacts/validation/20260714T*" \
  "$DEST/validation/"

echo "=== pull pod logs ==="
mkdir -p "$DEST/logs"
for f in pod_integration_grade.log pod_integration_grade_stdout.log \
  pod_release_grade_stdout.log pod_blackout_stdout.log pod_blackout_smoke.log \
  pod_cpu_loop.log pod_cpu_loop_stdout.log pod_cpu_chain.log pod_cpu_chain_stdout.log \
  pod_cpu_followon.log pod_cpu_followon_stdout.log pod_gebco_job.log pod_gebco_stdout.log \
  pod_int_harbor.log pod_int_deep.log pod_rel_harbor.log pod_rel_deep.log \
  pod_worst_harbor.log pod_worst_deep.log; do
  scp -P "$POD_PORT" -i "$POD_KEY" "$POD_HOST:/tmp/$f" "$DEST/logs/" 2>/dev/null || true
done

echo "=== write manifest ==="
ssh -o StrictHostKeyChecking=no -p "$POD_PORT" -i "$POD_KEY" "$POD_HOST" \
  'cd /workspace/Charybdis && git rev-parse HEAD && git status --short | head -20' \
  > "$DEST/git_state.txt" 2>&1 || true

cat > "$DEST/README.md" <<EOF
# L40S pod pull — hushed_black_coyote

- Pulled: ${STAMP} UTC
- Pod: ${POD_NAME} (${POD_HOST}:${POD_PORT})
- Repo path: /workspace/Charybdis

## Key runs (2026-07-14)

- \`deep_long_blackout\` fix verified (CEP95 ~1.16–1.22 m, was ~11.8 km)
- Integration grade: harbor 7/7 + deep 7/7 PASS
- Release tier 256-run: all PASS
- Worst-case 512-run sweep: all PASS
- GEBCO real-bathymetry job: eng + release PASS

## Highlights

| Artifact | Notes |
|---|---|
| \`validation/*/integration_grade/\` | Phase 1 pytest + eng 64×7 harbor+deep |
| \`validation/*/release_grade/\` | Release 256×7 harbor+deep |
| \`validation/*/worst_sweep/\` | 512-run worst scenarios |
| \`validation/*/blackout_smoke/\` | deep_long_blackout smoke |
| \`validation/*/real_bathymetry_job/\` | GEBCO tile + matcher validation |

Logs under \`logs/\`.
EOF

echo "PULL_COMPLETE dest=$DEST"
du -sh "$DEST" 2>/dev/null || true
