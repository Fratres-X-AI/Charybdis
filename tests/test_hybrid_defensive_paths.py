"""Defensive-path coverage for stable hybrid API contracts."""

from __future__ import annotations

import numpy as np
import pytest
from charybdis.hybrid import (
    BathymetryMap,
    BathymetryMatch,
    BathymetryMeasurement,
    BathymetryProfile,
    HybridFusionConfig,
    HybridNavigator,
    HybridNavState,
    HybridSensorFusion,
    MatchStatus,
    ModeManager,
    ModeManagerConfig,
    NavMode,
    PatrolExecutor,
    PatrolRoute,
    TerrainMatcherConfig,
    TerrainProfileMatcher,
    Waypoint,
)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"surface_depth_m": -1.0},
        {"surface_depth_m": 2.0, "submerged_depth_m": 2.0},
        {"submerged_depth_m": np.nan},
    ],
)
def test_mode_config_rejects_invalid_depth_thresholds(kwargs: dict) -> None:
    with pytest.raises(ValueError, match="mode depths"):
        ModeManagerConfig(**kwargs)


def test_mode_manager_covers_override_hint_only_and_invalid_depth() -> None:
    with pytest.raises(TypeError, match="hint_overrides_depth"):
        ModeManagerConfig(hint_overrides_depth=1)  # type: ignore[arg-type]

    manager = ModeManager(
        ModeManagerConfig(hint_overrides_depth=True),
        initial=NavMode.SUBMERGED,
    )
    assert manager.update(depth_m=9.0, hint=NavMode.SURFACE) == NavMode.SURFACE
    assert manager.update(depth_m=None, hint=NavMode.SUBMERGED) == NavMode.SUBMERGED
    assert manager.update(depth_m=None) == NavMode.SUBMERGED
    with pytest.raises(ValueError, match="depth_m"):
        manager.update(depth_m=-0.1)


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"init_pos_std": 0.0}, "positive"),
        ({"accel_noise": -1.0}, "non-negative"),
        ({"rejection_history_size": 0}, "history"),
        ({"max_recent_rejections": -1}, "recent"),
    ],
)
def test_fusion_config_rejects_invalid_limits(kwargs: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        HybridFusionConfig(**kwargs)


def _state(**changes: object) -> HybridNavState:
    values: dict[str, object] = {
        "pos": np.zeros(2),
        "vel": np.zeros(2),
        "cov": np.eye(8),
        "mode": NavMode.SURFACE,
        "t": 0.0,
    }
    values.update(changes)
    return HybridNavState(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"pos": np.zeros(3)}, "requires pos"),
        ({"vel": [np.nan, 0.0]}, "finite"),
        ({"cov": np.triu(np.ones((8, 8)))}, "symmetric"),
        ({"cov": np.diag([-1.0] + [1.0] * 7)}, "positive semidefinite"),
        ({"t": -1.0}, "state time"),
        ({"depth_m": -1.0}, "depth_m"),
        ({"depth_rate_mps": np.nan}, "depth_rate"),
    ],
)
def test_hybrid_state_rejects_invalid_snapshots(
    changes: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        _state(**changes)


def test_navigator_validates_components_exposes_properties_and_resumes() -> None:
    fusion = HybridSensorFusion([0.0, 0.0])
    patrol = PatrolExecutor(PatrolRoute((Waypoint([0.0, 0.0]), Waypoint([20.0, 0.0]))))
    with pytest.raises(TypeError, match="fusion"):
        HybridNavigator(object(), patrol)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="patrol"):
        HybridNavigator(fusion, object())  # type: ignore[arg-type]

    navigator = HybridNavigator(fusion, patrol)
    assert navigator.fusion is fusion
    assert navigator.patrol is patrol
    assert navigator.last_result is None

    result = navigator.resume(
        [19.0, 0.0],
        vel=[0.2, 0.0],
        pos_cov=np.eye(2),
        depth_m=0.0,
    )
    assert navigator.last_result is result
    assert result.command.waypoint_index == 1


def _map() -> BathymetryMap:
    y, x = np.mgrid[0:9, 0:9]
    return BathymetryMap(20.0 + x + 2.0 * y, 1.0)


def test_bathymetry_contract_defensive_paths() -> None:
    with pytest.raises(ValueError, match="finite"):
        BathymetryMap([[1.0, 2.0, 3.0], [4.0, np.nan, 6.0], [7.0, 8.0, 9.0]], 1.0)
    with pytest.raises(ValueError, match="at least 3x3"):
        BathymetryMap(np.ones((2, 2)), 1.0)
    with pytest.raises(ValueError, match="resolution_m"):
        BathymetryMap(np.ones((3, 3)), 0.0)
    with pytest.raises(ValueError, match="origin"):
        BathymetryMap(np.ones((3, 3)), 1.0, origin_xy_m=(np.nan, 0.0))

    bathymetry = _map()
    with pytest.raises(ValueError, match="shape"):
        bathymetry.contains([1.0, 2.0, 3.0])
    with pytest.raises(ValueError, match="finite"):
        bathymetry.sample([np.nan, 1.0])
    with pytest.raises(ValueError, match="outside"):
        bathymetry.sample([-1.0, 1.0])


def test_profile_matcher_rejects_invalid_contracts() -> None:
    with pytest.raises(ValueError, match="shape"):
        BathymetryProfile([0.0, 1.0, 2.0], [1.0, 2.0, 3.0])
    with pytest.raises(ValueError, match="at least three"):
        BathymetryProfile([[0.0, 0.0], [1.0, 0.0]], [1.0, 2.0])
    with pytest.raises(ValueError, match="variance_m2"):
        BathymetryProfile(
            [[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]],
            [1.0, 2.0, 3.0],
            variance_m2=0.0,
        )
    with pytest.raises(TypeError, match="remove_vertical_bias"):
        TerrainMatcherConfig(remove_vertical_bias=1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="BathymetryMap"):
        TerrainProfileMatcher(object())  # type: ignore[arg-type]

    bathymetry = _map()
    matcher = TerrainProfileMatcher(bathymetry)
    offsets = np.array([[-1.0, 0.0], [0.0, 0.0], [1.0, 0.0]])
    profile = BathymetryProfile(offsets, bathymetry.sample([4.0, 4.0] + offsets))
    with pytest.raises(ValueError, match="prior_pos"):
        matcher.match(profile, prior_pos=[1.0], prior_cov=np.eye(2))
    with pytest.raises(ValueError, match="prior_cov"):
        matcher.match(
            profile,
            prior_pos=[4.0, 4.0],
            prior_cov=[[1.0, 1.0], [0.0, 1.0]],
        )


def test_bathymetry_match_accepted_property() -> None:
    rejected = BathymetryMatch(MatchStatus.AMBIGUOUS)
    accepted = BathymetryMatch(
        MatchStatus.ACCEPTED,
        measurement=BathymetryMeasurement(
            pos_fix=[1.0, 2.0],
            pos_cov=np.eye(2),
        ),
    )

    assert not rejected.accepted
    assert accepted.accepted
