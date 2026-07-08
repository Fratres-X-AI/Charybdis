#!/usr/bin/env bash
# Enforce max 31 workers on pod; kill runaway pools.
set -e
echo "[$(date -u +%H:%M:%S)] killing stale python workers"
pkill -9 -f 'python.*pytest' 2>/dev/null || true
pkill -9 -f 'python.*pmf_' 2>/dev/null || true
pkill -9 -f 'python.*stress' 2>/dev/null || true
pkill -9 -f 'python.*charybdis' 2>/dev/null || true
sleep 2
echo "[$(date -u +%H:%M:%S)] python procs: $(pgrep -c python 2>/dev/null || echo 0)"
echo "[$(date -u +%H:%M:%S)] total procs: $(ps aux | wc -l)"
