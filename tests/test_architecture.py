import ast
import json
import subprocess
import sys
from pathlib import Path

import charybdis

ROOT = Path(__file__).resolve().parents[1]


def test_removed_root_compatibility_modules_do_not_exist():
    removed = {
        "navigator.py",
        "ekf.py",
        "pf.py",
        "pmf.py",
        "tercom.py",
        "simulation.py",
        "evaluate.py",
        "stress.py",
        "slam.py",
        "swarm.py",
        "nn_matcher.py",
    }

    assert not {path.name for path in (ROOT / "charybdis").iterdir()} & removed


def test_stable_hybrid_has_no_forbidden_dependencies():
    forbidden = {"legacy", "experimental", "console", "torch"}
    violations: list[str] = []
    for path in (ROOT / "charybdis" / "hybrid").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            module = None
            if isinstance(node, ast.ImportFrom):
                module = node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if any(part in forbidden for part in alias.name.split(".")):
                        violations.append(f"{path.name}:{alias.name}")
            if module and any(part in forbidden for part in module.split(".")):
                violations.append(f"{path.name}:{module}")

    assert violations == []


def test_root_import_is_pure_and_hybrid_focused():
    script = (
        "import json,sys,charybdis;"
        "print(json.dumps(sorted(name for name in sys.modules "
        "if name.startswith(('torch','matplotlib','scipy','netCDF4','rasterio',"
        "'console','charybdis.legacy','charybdis.experimental',"
        "'charybdis.simulation','charybdis.evaluation')))))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == []
    assert "HybridNavigator" in charybdis.__all__
    assert "Navigator" not in charybdis.__all__
    assert "SimConfig" not in charybdis.__all__


def test_examples_use_only_approved_charybdis_import_surfaces():
    allowed = {
        "charybdis",
        "charybdis.hybrid",
        "charybdis.legacy",
    }
    legacy_example_allowed = allowed | {
        "charybdis.config",
        "charybdis.imu",
        "charybdis.terrain",
    }
    deep_example_allowed = allowed | {
        "charybdis.evaluation",
        "charybdis.simulation",
    }
    pilot_example_allowed = allowed | {
        "charybdis.evaluation",
    }
    violations: list[str] = []
    for path in (ROOT / "examples").glob("*.py"):
        if path.name == "legacy_interceptor.py":
            allowed_for_file = legacy_example_allowed
        elif path.name in {"run_deep_patrol.py", "run_mission_preview.py"}:
            allowed_for_file = deep_example_allowed
        elif path.name == "verify_pilot_replay.py":
            allowed_for_file = pilot_example_allowed
        else:
            allowed_for_file = allowed
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
                if module.startswith("charybdis") and module not in allowed_for_file:
                    violations.append(f"{path.name}:{module}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name
                    if (
                        module.startswith("charybdis")
                        and module not in allowed_for_file
                    ):
                        violations.append(f"{path.name}:{module}")

    assert violations == []
