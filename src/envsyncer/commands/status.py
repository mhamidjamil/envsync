"""`envsyncer status` — show the sync plan without changing anything."""

from __future__ import annotations

from envsyncer.commands import _common
from envsyncer.core import cache
from envsyncer.core.profiles import resolve_active_profile
from envsyncer.core.session import open_session
from envsyncer.core.sync_engine import build_plan
from envsyncer.ui.console import info, success


def run(assume_yes: bool = False) -> None:
    session = open_session(assume_yes=assume_yes, need_repo=True)
    info(f"Project: [bold]{session.project_key}[/]")
    profile = resolve_active_profile(
        session.config, session.vault, session.project_key, assume_yes=assume_yes
    )

    local = _common.local_index(session)
    remote = _common.remote_index(session, profile)
    baseline = cache.load_baseline(session.project_key, profile)
    plan = build_plan(profile, local, remote, baseline)

    if not plan.files:
        info("No secret files found locally or in the vault for this profile.")
        return

    _common.render_plan(plan)
    if not plan.has_changes:
        success("Everything is in sync.")
