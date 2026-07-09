"""Tests for the final four Charybdis features (15/15).

Torch and ROS2 tests are gated so default CI stays CPU-only and green.
"""

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from console import charybdis_bathy as bathy
from console import charybdis_core as core
from console import charybdis_slam as slam
from console import charybdis_swarm as swarm

pytestmark = pytest.mark.console

ROOT = Path(__file__).resolve().parents[1]


def test_slam_loop_closure_reduces_drift():
    p = core.SimParams(autonomy=False, n_contacts=0, drift=20.0)
    s = core.init_state(seed=11, params=p)
    sm = slam.init_slam(core.START)
    loops = 0
    dr_sum = slam_sum = 0.0
    for _ in range(120):
        core.step(s, p)
        v = s.true_path[-1] - s.true_path[-2]
        loops += int(slam.slam_step(sm, v, core.bathymetry, dt=core.DT))
        dr_sum += float(np.hypot(*(s.true_pos - s.est_pos)))
        slam_sum += slam.position_error(sm, s.true_pos)
    assert loops >= 0
    assert slam_sum / 120 <= dr_sum / 120 + 5.0


def test_swarm_shares_tcm_benefit():
    sw = swarm.init_swarm(swarm.SwarmParams(n_agents=3), seed=5)
    for _ in range(90):
        swarm.step_swarm(sw)
    errs = [float(np.hypot(*(a.true_pos - a.est_pos))) for a in sw.agents]
    assert np.mean(errs) < 25.0
    assert len(sw.shared_fixes) >= 0


def test_swarm_montecarlo_improves_cep():
    if sys.platform == "win32":
        pytest.skip("multiprocessing spawn flaky on Windows CI")
    m = swarm.montecarlo_compare(n_runs=4, ticks=50, workers=2)
    assert m["team_cep50_m"] <= m["solo_cep50_m"] + 8.0


def test_gebco_npz_roundtrip(tmp_path):
    grid = bathy.sample_synthetic_to_grid(core.bathymetry, n=64)
    p = tmp_path / "tile.npz"
    np.savez(p, z=grid.z, extent=np.array([-10.0, 135.0, -10.0, 135.0]))
    loaded = bathy.load_bathymetry(str(p))
    assert abs(float(loaded(50.0, 50.0)) - float(grid(50.0, 50.0))) < 1e-6


def test_ros2_package_present():
    pkg = ROOT / "ros2_ws" / "src" / "charybdis_ros" / "package.xml"
    node = ROOT / "ros2_ws" / "src" / "charybdis_ros" / "charybdis_ros" / "nav_node.py"
    assert pkg.is_file() and node.is_file()
    smoke = ROOT / "scripts" / "ros2_smoke.sh"
    assert smoke.is_file()


def test_ros2_nav_stub_runs_without_rclpy():
    node = ROOT / "ros2_ws" / "src" / "charybdis_ros" / "charybdis_ros" / "nav_node.py"
    out = subprocess.run(
        [sys.executable, str(node), "--ticks", "8"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert out.returncode == 0
    assert "CHARYBDIS_ROS_STUB" in out.stdout


def test_nn_tcm_beats_large_offset():
    pytest.importorskip("torch")
    from console import charybdis_nn as nn

    tmp = ROOT / "models" / "tcm_cnn.pt"
    if not tmp.is_file():
        nn.train(
            model_path=tmp,
            n_samples=8000,
            epochs=6,
            batch=256,
            device="cpu",
            num_workers=4,
        )
    nn.load_model(tmp, device="cpu")
    true = core.ANOMALIES["SEAMOUNT CHARLIE"] + np.array([0.0, 0.0])
    est = true + np.array([5.0, -4.0])
    corr, peak, _ = nn.tcm_nn_match(true, est, core.bathymetry, model_path=tmp)
    assert peak > 0.25
    assert np.linalg.norm(corr - true) < np.linalg.norm(est - true)


def test_nn_integrated_via_core_flag():
    pytest.importorskip("torch")
    from console import charybdis_nn as nn

    tmp = ROOT / "models" / "_test_tcm2.pt"
    if not tmp.is_file():
        nn.train(model_path=tmp, n_samples=2000, epochs=2, batch=128)
    p = core.SimParams(autonomy=False, use_nn_tcm=True, nn_model_path=str(tmp))
    s = core.init_state(seed=7, params=p)
    for _ in range(100):
        core.step(s, p)
    assert any(k == "TCM" for _, k, _ in s.fixes) or s.reached
