#!/usr/bin/env bash
# Active RunPod endpoint — defaults below; override in pod_env.local.sh (gitignored).
#
# Use the "SSH over exposed TCP" command from the RunPod Connect tab, not the
# proxied ssh.runpod.io command. The direct TCP form supports SCP/SFTP.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SCRIPT_DIR/pod_env.local.sh" ]]; then
  # shellcheck source=scripts/pod/pod_env.local.sh
  source "$SCRIPT_DIR/pod_env.local.sh"
fi

export POD_NAME="${POD_NAME:-replace_me}"
export POD_HOST="${POD_HOST:-root@0.0.0.0}"
export POD_PORT="${POD_PORT:-22}"
export POD_KEY="${POD_KEY:-${HOME}/.ssh/id_ed25519}"
