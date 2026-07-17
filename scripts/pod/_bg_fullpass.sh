#!/usr/bin/env bash
ROOT="/c/Users/Besn Daddy/Desktop/Syren GDI_tmp"
nohup bash "$ROOT/scripts/pod/_pull_fullpass_only.sh" \
  > "$ROOT/artifacts/fullpass_pull.out" 2>&1 &
echo "STARTED_PID=$!"
sleep 1
ps -ef | grep _pull_fullpass_only | grep -v grep || true
