"""Process limits: 31 for standalone MC scripts only; 1 inside pytest."""
from __future__ import annotations
import os, sys
MAX_WORKERS = 31

def pool_workers(requested: int | None = None) -> int:
    if "pytest" in sys.modules or os.environ.get("PYTEST_XDIST_WORKER"):
        return 1
    n = MAX_WORKERS if requested is None else min(int(requested), MAX_WORKERS)
    return max(1, n)
