"""`envsyncer` (default) — detect the repo, resolve the profile, sync."""

from __future__ import annotations

from envsyncer.commands import _common
from envsyncer.core.profiles import resolve_active_profile
from envsyncer.core.session import open_session
from envsyncer.ui.console import info


def run(assume_yes: bool = False) -> None:
    session = open_session(assume_yes=assume_yes, need_repo=True)
    info(f"Project: [bold]{session.project_key}[/]")
    profile = resolve_active_profile(
        session.config, session.vault, session.project_key, assume_yes=assume_yes
    )
    _common.run_sync(session, profile)
