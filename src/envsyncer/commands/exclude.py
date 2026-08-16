"""`envsyncer exclude [pattern]` — register an extra glob to skip.

With no argument it lists the exclude patterns in effect. With a pattern (e.g.
``*.local``, ``config.dev.json`` or a full path) it saves it so matching files
are never synced, even if they also match a secret pattern. A bare name matches
anywhere in the project; a pattern containing a slash is a path relative to the
project root, and a full absolute path is reduced to one. Applies to all
projects.

``--remove`` takes a pattern back out again. For path exclusions that belong to
a single repo, a ``.envsyncignore`` file (gitignore syntax) is a better home.
"""

from __future__ import annotations

from envsyncer.core.config import Config
from envsyncer.core.discovery import DEFAULT_EXCLUDE_PATTERNS
from envsyncer.ui.console import info, plain, success, warn


def run(pattern: str | None = None, remove: bool = False, assume_yes: bool = False) -> None:  # noqa: ARG001
    config = Config.load()
    if pattern is None:
        _list(config)
        return

    if remove:
        if config.remove_exclude(pattern):
            config.save()
            success(f"Removed exclude pattern [bold]{pattern}[/] — no longer skipped.")
        else:
            warn(f"Pattern '{pattern}' was not in the list.")
        _list(config)
        return

    if config.add_exclude(pattern):
        if config.remove_include(pattern):
            warn(f"'{pattern}' was in the include list — removed it so this takes effect.")
        config.save()
        success(f"Added exclude pattern [bold]{pattern}[/] — skipped from now on.")
        info("Anything already in the vault stays there: `envsyncer delete <path>` removes it.")
    else:
        warn(f"Pattern '{pattern}' is already excluded.")
    _list(config)


def _list(config: Config) -> None:
    info("Exclude patterns currently in effect:")
    for p in DEFAULT_EXCLUDE_PATTERNS:
        plain(f"  • {p} [dim](default)[/]")
    for p in config.exclude_patterns():
        plain(f"  • {p} [green](custom)[/]")
