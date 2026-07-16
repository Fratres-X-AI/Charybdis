from charybdis.config import SimConfig
from charybdis.simulation import (
    HybridHarborConfig,
    run_hybrid_harbor_simulation,
    run_simulation,
)


def _rounded(summary: dict, digits: int = 8) -> dict:
    return {
        key: round(value, digits) if isinstance(value, float) else value
        for key, value in summary.items()
    }


def test_hybrid_harbor_golden_summary():
    summary = _rounded(
        run_hybrid_harbor_simulation(HybridHarborConfig(seed=9)).summary()
    )

    assert summary == {
        "bathy_matches_accepted": 9,
        "bathy_matches_attempted": 9,
        "depth_anees": 1.07045714,
        "filter_healthy": True,
        "final_depth_error_m": 0.18723989,
        "final_error_m": 0.82453092,
        "fusion_rejections": 0,
        "last_bathy_t": 73.0,
        "last_gps_t": 90.0,
        "max_error_m": 2.17722626,
        "max_gps_reacquisition_jump_m": 3.47520919,
        "mean_error_m": 0.8528732,
        "position_anees": 2.40385966,
        "route_complete": True,
        "scenario": "hybrid_harbor",
        "steps": 91,
        "used_submerged": True,
        "used_surface": True,
    }


def test_legacy_simulation_golden_summary():
    summary = _rounded(
        run_simulation(
            SimConfig(
                duration=0.2,
                seed=7,
                use_pf=False,
                use_pmf=False,
                use_tercom=False,
            )
        ).summary()
    )

    assert summary == {
        "ekf_final_m": 17.60926994,
        "ekf_max_m": 17.60926994,
        "ekf_rmse_m": 17.58734259,
        "ins_final_m": 4.60285901,
        "ins_max_m": 4.60285901,
        "ins_rmse_m": 4.60061111,
        "n_tercom_fixes": 0,
    }
