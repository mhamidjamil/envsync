"""`envsyncer push` — upload all local secrets to the active profile."""

from __future__ import annotations

from envsyncer.commands import _common
from envsyncer.core.profiles import resolve_active_profile
from envsyncer.core.session import open_session


def run(assume_yes: bool = False) -> None:
    session = open_session(assume_yes=assume_yes, need_repo=True)
    profile = resolve_active_profile(
        session.config, session.vault, session.project_key, assume_yes=assume_yes
    )
    _common.run_push(session, profile)
