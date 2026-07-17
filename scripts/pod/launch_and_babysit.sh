#!/usr/bin/env bash
# Alias for the 2x H200 SXM end-to-end runner.
exec bash "$(cd "$(dirname "$0")" && pwd)/go_h200_sxm.sh" "$@"
