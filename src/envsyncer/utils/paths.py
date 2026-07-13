"""Filesystem locations used by EnvSyncer.

Everything lives under ``~/.envsyncer`` so behaviour is identical on macOS,
Windows and Linux (``Path.home()`` resolves correctly on all three).
"""

from __future__ import annotations

from pathlib import Path

#: Root config directory, e.g. ``/Users/alice/.envsyncer``.
CONFIG_DIR: Path = Path.home() / ".envsyncer"

#: Main configuration file (holds the GitHub token and per-project settings).
CONFIG_FILE: Path = CONFIG_DIR / "config.json"

#: Directory for rotating log files.
LOGS_DIR: Path = CONFIG_DIR / "logs"

#: Directory for baseline hash caches (used to detect two-sided changes).
CACHE_DIR: Path = CONFIG_DIR / "cache"


def ensure_dirs() -> None:
    """Create the config/logs/cache directories if they do not yet exist."""
    for directory in (CONFIG_DIR, LOGS_DIR, CACHE_DIR):
        directory.mkdir(parents=True, exist_ok=True)
