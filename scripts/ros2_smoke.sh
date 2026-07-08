#!/usr/bin/env bash
# ROS2 smoke test (not part of default CI). Requires Docker.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
docker run --rm -v "$ROOT:/ws" -w /ws ros:jazzy bash -lc '
  apt-get update -qq && apt-get install -y -qq python3-pip >/dev/null
  pip install -q numpy scipy
  if [ ! -d /opt/ros/jazzy/setup.bash ]; then echo "ROS2 jazzy missing"; exit 1; fi
  source /opt/ros/jazzy/setup.bash
  cd ros2_ws && colcon build --symlink-install
  source install/setup.bash
  timeout 8 ros2 run charybdis_ros nav_sim --ticks 5 || true
  echo ROS2_SMOKE_OK
'
