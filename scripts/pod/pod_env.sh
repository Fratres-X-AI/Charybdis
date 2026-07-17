#!/usr/bin/env bash
# Active RunPod endpoint - copy this file locally or edit before a run.
#
# Use the "SSH over exposed TCP" command from the RunPod Connect tab, not the
# proxied ssh.runpod.io command. The direct TCP form supports SCP/SFTP.
export POD_NAME="${POD_NAME:-replace_me}"
export POD_HOST="${POD_HOST:-root@0.0.0.0}"
export POD_PORT="${POD_PORT:-22}"
export POD_KEY="${POD_KEY:-/c/Users/YourName/.ssh/id_ed25519}"
