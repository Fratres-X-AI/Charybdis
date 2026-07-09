"""Match a bottom-depth profile and fuse only an accepted terrain fix."""

from __future__ import annotations

import numpy as np
from charybdis import (
    BathymetryMap,
    HybridSensorFusion,
    NavMode,
    SensorPacket,
    TerrainProfileMatcher,
)
from charybdis.hybrid import (
    BathymetryProfile,
    DepthMeasurement,
    ImuMeasurement,
    MatchStatus,
    TerrainMatcherConfig,
)


def build_map() -> BathymetryMap:
    """Create a distinctive positive-down map in a local metric frame."""
    axis = np.arange(0.0, 101.0)
    x_grid, y_grid = np.meshgrid(axis, axis)
    depth_m = (
        30.0
        + 4.0 * np.sin(x_grid / 7.0)
        + 3.0 * np.cos(y_grid / 9.0)
        + 2.0 * np.sin((x_grid + y_grid) / 5.0)
    )
    return BathymetryMap(depth_m, resolution_m=1.0)


def main() -> None:
    """Produce a quality-gated fix and pass it through the fusion contract."""
    bathymetry_map = build_map()
    true_position = np.array([50.0, 55.0])
    prior_position = np.array([57.0, 49.0])
    prior_covariance = np.diag([10.0, 10.0]) ** 2

    axis = np.array([-8.0, 0.0, 8.0])
    x_offsets, y_offsets = np.meshgrid(axis, axis)
    offsets = np.column_stack((x_offsets.ravel(), y_offsets.ravel()))
    profile = BathymetryProfile(
        offsets_xy_m=offsets,
        bottom_depth_m=bathymetry_map.sample(true_position + offsets),
        variance_m2=0.2**2,
        timestamp_s=1.0,
    )
    matcher = TerrainProfileMatcher(
        bathymetry_map,
        TerrainMatcherConfig(
            search_radius_m=15.0,
            grid_step_m=1.0,
            min_cost_margin=0.1,
        ),
    )
    match = matcher.match(
        profile,
        prior_pos=prior_position,
        prior_cov=prior_covariance,
    )
    if match.status != MatchStatus.ACCEPTED or match.measurement is None:
        raise RuntimeError(f"expected an accepted profile match, got {match.status}")

    fusion = HybridSensorFusion(
        pos0=prior_position,
        depth0=8.0,
        initial_mode=NavMode.SUBMERGED,
    )
    fused = fusion.step(
        SensorPacket(
            imu=ImuMeasurement([0.0, 0.0], dt=1.0, timestamp_s=1.0),
            depth=DepthMeasurement(8.0, timestamp_s=1.0),
            bathymetry=match.measurement,
            timestamp_s=1.0,
        )
    )

    prior_error = float(np.linalg.norm(prior_position - true_position))
    fused_error = float(np.linalg.norm(fused.pos - true_position))
    if fused_error >= prior_error:
        raise RuntimeError("accepted terrain fix did not improve this example")

    print(f"status={match.status.value}")
    print(f"candidates={match.candidates_evaluated}")
    print(f"matched_position={match.measurement.pos_fix.tolist()}")
    print(f"prior_error_m={prior_error:.2f}")
    print(f"fused_error_m={fused_error:.2f}")


if __name__ == "__main__":
    main()
