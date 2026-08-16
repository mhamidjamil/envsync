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

    remote = _common.remote_index(session, profile)
    scan = _common.scan_local(session, remote)
    baseline = cache.load_baseline(session.project_key, profile)
    plan = build_plan(profile, scan.files, remote, baseline, excluded=scan.excluded)

    if not plan.files:
        info("No secret files found locally or in the vault for this profile.")
        return

    _common.render_plan(plan)
    if plan.has_changes:
        _common.render_hints(plan)
    else:
        success("Everything is in sync.")
