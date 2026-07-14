#!/usr/bin/env bash
# Hour sprint: highres NOAA bathy -> integration grade (31 workers max).
set -euo pipefail
REPO=/workspace/Charybdis
cd "$REPO"
LOG=/tmp/pod_hour_sprint.log
: >"$LOG"
ts() { date -u +"%H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

log "HOUR_SPRINT_START"
bash scripts/pod/pod_highres_bathy.sh 2>&1 | tee -a "$LOG"
log "integration_grade start"
bash scripts/pod/pod_integration_grade.sh 2>&1 | tee -a "$LOG"
log "HOUR_SPRINT_COMPLETE"
