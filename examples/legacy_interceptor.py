"""Use the maintained interceptor Navigator through its explicit legacy API."""

from __future__ import annotations

import numpy as np
from charybdis.config import SimConfig
from charybdis.imu import ImuSample
from charybdis.legacy import NavEstimate, Navigator
from charybdis.terrain import Terrain


def main() -> None:
    """Run one legacy EKF/TRN cycle without importing it from package root."""
    cfg = SimConfig(
        dt=0.1,
        terrain_size=2_000.0,
        terrain_res=25.0,
        terrain_relief=100.0,
        use_tercom=False,
        use_pf=False,
        use_pmf=False,
        filter_fusion=False,
        mode_mgmt=False,
    )
    terrain = Terrain.synthetic(cfg)
    initial_position = np.array([1_000.0, 1_000.0])
    initial_velocity = np.array([2.0, 0.0])
    navigator = Navigator(
        cfg,
        terrain,
        pos0=initial_position,
        vel0=initial_velocity,
    )

    expected_position = initial_position + initial_velocity * cfg.dt
    ground_elevation = float(terrain.elevation(*expected_position))
    sample = ImuSample(
        accel=np.zeros(2),
        heading=0.0,
        baro_alt=ground_elevation + cfg.cruise_alt,
        agl=cfg.cruise_alt,
        ground_elev=ground_elevation,
    )
    navigator.step(sample, t=cfg.dt)
    estimate: NavEstimate = navigator.estimate(source="ekf", t=cfg.dt)

    if estimate.source != "ekf" or not np.all(np.isfinite(estimate.pos)):
        raise RuntimeError("legacy Navigator did not return a finite EKF estimate")

    print("api=charybdis.legacy.Navigator")
    print(f"source={estimate.source}")
    print(f"position_m={estimate.pos.round(3).tolist()}")
    print(f"position_std_m={estimate.pos_std.round(3).tolist()}")
    print(f"ekf_healthy={estimate.ekf_healthy}")


if __name__ == "__main__":
    main()
