#!/usr/bin/env bash
# Babysit only — assumes lanes already running. Use launch_and_babysit.sh for cold start.
cd "$(dirname "$0")/../.."
chmod +x scripts/pod/*.sh
exec bash scripts/pod/babysit_h200_elite.sh "$@"
