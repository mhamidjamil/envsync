"""`envsyncer add [pattern]` — register an extra secret filename/glob.

With no argument it lists the patterns currently scanned. With a pattern (e.g.
``local.properties``, ``android/local.properties`` or ``*.pem``) it saves it so
every future scan includes it. A bare name matches anywhere in the project; a
pattern containing a slash is a path relative to the project root. Patterns
apply to all projects, matching the way the built-in patterns do.

``--remove`` takes a pattern back out again.
"""

from __future__ import annotations

from envsyncer.core.config import Config
from envsyncer.core.discovery import DEFAULT_SECRET_PATTERNS
from envsyncer.ui.console import info, plain, success, warn


def run(pattern: str | None = None, remove: bool = False, assume_yes: bool = False) -> None:  # noqa: ARG001
    config = Config.load()
    if pattern is None:
        _list(config)
        return

    if remove:
        if config.remove_include(pattern):
            config.save()
            success(f"Removed secret pattern [bold]{pattern}[/] — no longer scanned for.")
        else:
            warn(f"Pattern '{pattern}' was not in the list.")
        _list(config)
        return

    if config.add_include(pattern):
        # The same pattern on both lists can only mean the exclude won and the
        # file quietly stopped syncing, so the newer intent wins outright.
        if config.remove_exclude(pattern):
            warn(f"'{pattern}' was in the exclude list — removed it so this takes effect.")
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
