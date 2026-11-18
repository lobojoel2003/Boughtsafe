"""Boughtsafe: recall alerts matched to what you actually bought."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("boughtsafe")
except PackageNotFoundError:  # pragma: no cover - running from a source checkout
    __version__ = "0.0.0+source"
