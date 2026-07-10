"""`envsyncer add [pattern]` — register an extra secret filename/glob.

With no argument it lists the patterns currently scanned. With a pattern (e.g.
``local.properties`` or ``*.pem``) it saves it so every future scan includes it.
Patterns apply to all projects, matching the way the built-in patterns do.
"""

from __future__ import annotations

from envsyncer.core.config import Config
from envsyncer.core.discovery import DEFAULT_SECRET_PATTERNS
from envsyncer.ui.console import info, plain, success, warn


def run(pattern: str | None = None, assume_yes: bool = False) -> None:  # noqa: ARG001
    config = Config.load()
    if pattern is None:
        _list(config)
        return

    if config.add_include(pattern):
        config.save()
        success(f"Added secret pattern [bold]{pattern}[/] — included from now on.")
    else:
        warn(f"Pattern '{pattern}' is already registered.")
    _list(config)


def _list(config: Config) -> None:
    info("Secret patterns currently scanned:")
    for p in DEFAULT_SECRET_PATTERNS:
        plain(f"  • {p} [dim](default)[/]")
    for p in config.include_patterns():
        plain(f"  • {p} [green](custom)[/]")
