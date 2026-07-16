#!/usr/bin/env bash
cd "$(dirname "$0")/../.."
chmod +x scripts/pod/*.sh
exec bash scripts/pod/babysit_quad_cluster.sh
