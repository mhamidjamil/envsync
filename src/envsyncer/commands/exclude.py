"""`envsyncer exclude [pattern]` — register an extra glob to skip.

With no argument it lists the exclude patterns in effect. With a pattern (e.g.
``*.local`` or ``config.dev.json``) it saves it so matching files are never
synced, even if they also match a secret pattern. Applies to all projects.

For path-specific exclusions within a single repo, use a ``.envsyncignore``
file (gitignore syntax) instead.
"""

from __future__ import annotations

from envsyncer.core.config import Config
from envsyncer.core.discovery import DEFAULT_EXCLUDE_PATTERNS
from envsyncer.ui.console import info, plain, success, warn


def run(pattern: str | None = None, assume_yes: bool = False) -> None:  # noqa: ARG001
    config = Config.load()
    if pattern is None:
        _list(config)
        return

    if config.add_exclude(pattern):
        config.save()
        success(f"Added exclude pattern [bold]{pattern}[/] — skipped from now on.")
    else:
        warn(f"Pattern '{pattern}' is already excluded.")
    _list(config)


def _list(config: Config) -> None:
    info("Exclude patterns currently in effect:")
    for p in DEFAULT_EXCLUDE_PATTERNS:
        plain(f"  • {p} [dim](default)[/]")
    for p in config.exclude_patterns():
        plain(f"  • {p} [green](custom)[/]")
