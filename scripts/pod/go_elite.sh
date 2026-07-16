#!/usr/bin/env bash
cd "$(dirname "$0")/../.."
chmod +x scripts/pod/*.sh
exec bash scripts/pod/launch_elite_phase34.sh
