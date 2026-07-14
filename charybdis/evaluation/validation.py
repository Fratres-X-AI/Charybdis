"""Reproducible validation manifests and JSON artifact helpers."""

from __future__ import annotations

import json
import os
import platform
import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from ..version import __version__

VALIDATION_ARTIFACT_SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class ValidationManifest:
    """Minimum provenance required for a reproducible validation artifact."""

    git_sha: str
    seeds: tuple[int, ...]
    workers: int
    scenario: str
    config: Mapping[str, Any] = field(default_factory=dict)
    created_utc: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    charybdis_version: str = __version__
    python_version: str = platform.python_version()
    numpy_version: str = np.__version__
    platform: str = sys.platform

    def __post_init__(self) -> None:
        if not self.git_sha.strip():
            raise ValueError("git_sha is required")
        if not self.seeds or any(seed < 0 for seed in self.seeds):
            raise ValueError("seeds must be non-empty and non-negative")
        if len(set(self.seeds)) != len(self.seeds):
            raise ValueError("seeds must be unique")
        if not 1 <= self.workers <= 31:
            raise ValueError("workers must be between 1 and 31")
        if not self.scenario.strip():
            raise ValueError("scenario is required")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible manifest."""
        result = asdict(self)
        result["seeds"] = list(self.seeds)
        result["config"] = dict(self.config)
        return result


def load_validation_seeds(
    path: str | os.PathLike[str],
    *,
    limit: int | None = None,
) -> tuple[int, ...]:
    """Load unique integer seeds, ignoring blank lines and comments."""
    values: list[int] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.split("#", 1)[0].strip()
        if stripped:
            values.append(int(stripped))
    if not values or any(value < 0 for value in values):
        raise ValueError("seed file must contain non-negative integers")
    if len(set(values)) != len(values):
        raise ValueError("seed file contains duplicates")
    if limit is not None:
        if limit <= 0:
            raise ValueError("limit must be positive")
        values = values[:limit]
    return tuple(values)


def write_validation_artifact(
    path: str | os.PathLike[str],
    *,
    manifest: ValidationManifest,
    results: Mapping[str, Any],
) -> Path:
    """Atomically write one validation artifact as formatted JSON."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": VALIDATION_ARTIFACT_SCHEMA_VERSION,
        "manifest": manifest.to_dict(),
        "results": _json_value(results),
    }
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination


def _json_value(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_json_value(item) for item in value]
    return value


__all__ = [
    "VALIDATION_ARTIFACT_SCHEMA_VERSION",
    "ValidationManifest",
    "load_validation_seeds",
    "write_validation_artifact",
]
