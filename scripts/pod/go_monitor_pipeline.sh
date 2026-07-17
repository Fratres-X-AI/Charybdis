#!/usr/bin/env bash
# Monitor remote validation pipeline until all gates pass. Wrapper for internal script.
cd "$(dirname "$0")/../.."
chmod +x scripts/pod/*.sh
exec bash scripts/pod/babysit_h200_elite.sh "$@"
