"""Property checks for numerical invariants on the stable hybrid path."""

from __future__ import annotations

import numpy as np
from charybdis.hybrid import (
    BathymetryMap,
    DepthMeasurement,
    HybridSensorFusion,
    ImuMeasurement,
    SensorPacket,
    VelocityMeasurement,
)
from hypothesis import given, settings
from hypothesis import strategies as st


@settings(max_examples=30, deadline=None)
@given(
    accelerations=st.lists(
        st.tuples(
            st.floats(-1.0, 1.0, allow_nan=False, allow_infinity=False),
            st.floats(-1.0, 1.0, allow_nan=False, allow_infinity=False),
        ),
        min_size=1,
        max_size=20,
    ),
)
def test_fusion_covariance_stays_psd_for_finite_packets(
    accelerations: list[tuple[float, float]],
) -> None:
    fusion = HybridSensorFusion(pos0=[0.0, 0.0], depth0=2.0)

    for index, acceleration in enumerate(accelerations, start=1):
        state = fusion.step(
            SensorPacket(
                imu=ImuMeasurement(acceleration, dt=0.1, timestamp_s=index * 0.1),
                depth=DepthMeasurement(2.0, var=0.04, timestamp_s=index * 0.1),
                velocity=VelocityMeasurement(
                    [0.0, 0.0],
                    cov=np.eye(2) * 0.01,
                    timestamp_s=index * 0.1,
                ),
                timestamp_s=index * 0.1,
            )
        )

        assert np.all(np.isfinite(state.cov))
        assert np.linalg.eigvalsh(state.cov).min() >= -1e-9
        assert state.depth_m >= 0.0


@given(
    row=st.integers(min_value=0, max_value=9),
    column=st.integers(min_value=0, max_value=9),
)
def test_bathymetry_sampling_is_exact_at_grid_nodes(row: int, column: int) -> None:
    grid = np.arange(100, dtype=np.float64).reshape(10, 10) + 10.0
    bathymetry = BathymetryMap(
        grid,
        resolution_m=2.0,
        origin_xy_m=(-4.0, 6.0),
    )
    point = np.array([-4.0 + 2.0 * column, 6.0 + 2.0 * row])

    sampled = bathymetry.sample(point)

    assert np.isclose(float(sampled), grid[row, column], atol=1e-8)
