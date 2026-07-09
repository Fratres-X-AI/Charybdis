import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "slow: long-running sim/Monte-Carlo integration test; skipped on CI "
        "(validated on the pod). Force with RUN_SLOW=1.",
    )


def pytest_collection_modifyitems(config, items):
    # Heavy multi-second simulation/MC tests run on the pod, not on GitHub
    # runners. Skip them on CI unless explicitly opted in.
    on_ci = os.environ.get("GITHUB_ACTIONS") == "true"
    if not on_ci or os.environ.get("RUN_SLOW") == "1":
        return
    skip_slow = pytest.mark.skip(
        reason="slow integration test; validated on pod (set RUN_SLOW=1)"
    )
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)
