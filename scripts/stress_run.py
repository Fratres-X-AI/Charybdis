"""Pod stress harness runner (31 workers).

Usage: python scripts/stress_run.py [n_seeds]
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

from charybdis.evaluation import default_stress_cases, run_stress_harness, stress_report


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 64
    seeds = list(range(1, n + 1))
    results = run_stress_harness(default_stress_cases(), seeds=seeds, n_workers=31)
    print(stress_report(results))
    if not all(r.passed for r in results if r.required):
        sys.exit(1)


if __name__ == "__main__":
    main()
