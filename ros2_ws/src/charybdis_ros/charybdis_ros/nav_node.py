#!/usr/bin/env python3
"""ROS2 node: publishes Charybdis nav telemetry, subscribes to ping commands."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# repo root on PYTHONPATH when launched from ros2_ws after colcon build
ROOT = Path(__file__).resolve()
for candidate in [ROOT, *ROOT.parents]:
    if (candidate / "console" / "charybdis_core.py").exists():
        ROOT = candidate
        break
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from console import charybdis_core as core


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticks", type=int, default=20)
    parser.add_argument("--seed", type=int, default=7)
    args, _ = parser.parse_known_args()

    try:
        import rclpy
        from rclpy.node import Node
        from geometry_msgs.msg import Point
        from std_msgs.msg import Float32, Empty
    except ImportError:
        # headless import check for smoke scripts without full ROS graph
        p = core.SimParams(autonomy=False)
        s = core.init_state(seed=args.seed, params=p)
        for _ in range(args.ticks):
            core.step(s, p)
        print(f"CHARYBDIS_ROS_STUB ticks={args.ticks} defl={s.telemetry[-1]['deflection']:.2f}")
        return

    class NavNode(Node):
        def __init__(self):
            super().__init__("charybdis_nav")
            self.pub_true = self.create_publisher(Point, "true_pos", 10)
            self.pub_est = self.create_publisher(Point, "est_pos", 10)
            self.pub_defl = self.create_publisher(Float32, "deflection", 10)
            self.create_subscription(Empty, "ping", self._ping, 10)
            self.params = core.SimParams(autonomy=False)
            self.state = core.init_state(seed=args.seed, params=self.params)
            self.timer = self.create_timer(0.2, self._tick)
            self.max_ticks = args.ticks

        def _ping(self, _msg):
            core.request_ping(self.state)

        def _tick(self):
            if self.state.reached or self.state.tick >= self.max_ticks:
                self.get_logger().info("sim complete")
                raise SystemExit(0)
            core.step(self.state, self.params)
            tp = Point(x=float(self.state.true_pos[0]), y=float(self.state.true_pos[1]), z=0.0)
            ep = Point(x=float(self.state.est_pos[0]), y=float(self.state.est_pos[1]), z=0.0)
            self.pub_true.publish(tp)
            self.pub_est.publish(ep)
            self.pub_defl.publish(Float32(data=float(self.state.telemetry[-1]["deflection"])))

    rclpy.init()
    node = NavNode()
    try:
        rclpy.spin(node)
    except SystemExit:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
