"""`envsyncer profile [name]` — view or switch the active profile."""

from __future__ import annotations

from envsyncer.core.profiles import DEFAULT_PROFILE, switch_profile
from envsyncer.core.session import open_session
from envsyncer.ui.console import info, plain, success


def run(name: str | None = None, assume_yes: bool = False) -> None:
    session = open_session(assume_yes=assume_yes, need_repo=True)
    key = session.project_key
    active = session.config.get_profile(key)
    available = session.vault.list_profiles(key)

    if name is None:
        _show(active, available)
        return

    switch_profile(session.config, key, name)
    if name in available:
        success(f"Active profile set to [bold]{name}[/].")
    else:
        success(f"Active profile set to [bold]{name}[/] (new — created on next sync/push).")


def _show(active: str | None, available: list[str]) -> None:
    info(f"Active profile: [bold]{active or f'{DEFAULT_PROFILE} (default)'}[/]")
    if available:
        plain("Available profiles in vault:")
        for name in available:
            marker = " [green](active)[/]" if name == active else ""
            plain(f"  • {name}{marker}")
    else:
        plain("[dim]No profiles in the vault yet — the first sync creates one.[/]")
