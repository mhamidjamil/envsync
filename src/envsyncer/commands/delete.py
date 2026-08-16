"""`envsyncer delete [path…]` — remove files from the vault.

Only the vault copy goes; whatever is on this machine stays exactly as it is.
Use it when a file was synced by mistake, was renamed, or is no longer a secret
this project needs — otherwise it keeps coming back as "remote only" on every
machine that clones the repo.

With no argument it lists what the active profile holds and lets you pick one.
"""

from __future__ import annotations

from envsyncer.commands import _common
from envsyncer.core.profiles import resolve_active_profile
from envsyncer.core.session import Session, open_session
from envsyncer.models import RemoteFile
from envsyncer.ui import prompts
from envsyncer.ui.console import info, plain, warn
from envsyncer.utils.errors import UserAbort


def run(paths: list[str] | None = None, assume_yes: bool = False) -> None:
    session = open_session(assume_yes=assume_yes, need_repo=True)
    info(f"Project: [bold]{session.project_key}[/]")
    profile = resolve_active_profile(
        session.config, session.vault, session.project_key, assume_yes=assume_yes
    )

    remote = _common.remote_index(session, profile)
    if not remote:
        warn(f"Profile '{profile}' has no files in the vault.")
        return

    targets = _resolve_targets(session, remote, list(paths or []))
    if not targets:
        return

    plain("")
    for rel in targets:
        local_note = " [dim](your local copy stays)[/]" if (session.root / rel).exists() else ""
        plain(f"  [red]✂[/] {rel}{local_note}")

    if not prompts.confirm(
        f"Permanently delete {len(targets)} file(s) from vault profile '{profile}'?",
        assume_yes=assume_yes,
        default=False,
    ):
        info("Cancelled — nothing was deleted.")
        return

    _common.run_delete(session, profile, targets)


def _resolve_targets(
    session: Session, remote: dict[str, RemoteFile], requested: list[str]
) -> list[str]:
    if not requested:
        return _pick_one(remote)

    targets, unknown = [], []
    for raw in requested:
        rel = _match(session, remote, raw)
        (targets if rel else unknown).append(rel or raw)
    if unknown:
        warn(f"Not in profile: {', '.join(unknown)}")
        plain("[dim]Tracked files:[/]")
        for rel in sorted(remote):
            plain(f"  • {rel}")
        raise UserAbort("Nothing deleted.")
    return sorted(set(targets))


def _match(session: Session, remote: dict[str, RemoteFile], raw: str) -> str | None:
    """Accept a vault-relative path, or any path/name that resolves to one."""
    candidate = raw.strip().replace("\\", "/")
    if candidate in remote:
        return candidate
    if session.root is not None:
        try:
            relative = (session.root / candidate).resolve().relative_to(session.root.resolve())
        except (ValueError, OSError):
            relative = None
        if relative is not None and relative.as_posix() in remote:
            return relative.as_posix()
    matches = [rel for rel in remote if rel.rsplit("/", 1)[-1] == candidate]
    return matches[0] if len(matches) == 1 else None


def _pick_one(remote: dict[str, RemoteFile]) -> list[str]:
    tracked = sorted(remote)
    choice = prompts.select(
        "Which file should be deleted from the vault?",
        [*tracked, "Cancel"],
        default_index=len(tracked),
    )
    if choice >= len(tracked):
        info("Cancelled.")
        return []
    return [tracked[choice]]
