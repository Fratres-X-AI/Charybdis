#!/usr/bin/env bash
# Monitor remote validation pipeline until all gates pass.
# Cold start (new/restarted pod): bash scripts/pod/launch_and_babysit.sh
cd "$(dirname "$0")/../.."
chmod +x scripts/pod/*.sh
exec bash scripts/pod/babysit_until_green.sh "$@"
