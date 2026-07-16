#!/usr/bin/env python3
"""Generate frozen holdout seeds disjoint from seeds_v1."""
from __future__ import annotations

import pathlib

import numpy as np


def main() -> None:
    v1 = {
        int(x)
        for x in pathlib.Path("validation/seeds_v1.txt").read_text().split()
        if x.strip().isdigit()
    }
    rng = np.random.default_rng(20260716)
    holdout: list[int] = []
    while len(holdout) < 512:
        seed = int(rng.integers(1, 2**31 - 1))
        if seed not in v1 and seed not in holdout:
            holdout.append(seed)
    path = pathlib.Path("validation/seeds_holdout_v1.txt")
    path.write_text(
        "# Frozen holdout seeds v1 — never tune against these\n"
        + "\n".join(str(seed) for seed in holdout)
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {path} count={len(holdout)}")


if __name__ == "__main__":
    main()
