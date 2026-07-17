#!/usr/bin/env bash
# Long-running pipeline monitor with incremental artifact pulls.
cd "$(dirname "$0")/../.."
chmod +x scripts/pod/*.sh
exec bash scripts/pod/babysit_away.sh "$@"
