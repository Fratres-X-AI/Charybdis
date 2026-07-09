"""Installed package version."""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("charybdis")
except PackageNotFoundError:
    __version__ = "0.2.0"

__all__ = ["__version__"]
