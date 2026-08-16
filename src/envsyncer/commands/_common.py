"""Shared building blocks for the sync/status/push/pull/delete commands."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import NamedTuple

from rich.table import Table

from envsyncer.commands import conflict
from envsyncer.commands.conflict import ConflictDecision
from envsyncer.core import cache
from envsyncer.core.discovery import adopt_tracked, discover_secrets
from envsyncer.core.profiles import SUGGESTED_NEW_PROFILE
from envsyncer.core.session import Session
from envsyncer.core.sync_engine import build_plan
from envsyncer.models import FilePlan, RemoteFile, SecretFile, SyncAction, SyncPlan
from envsyncer.ui import prompts
from envsyncer.ui.console import console, downloaded, info, plain, removed, success, uploaded, warn
from envsyncer.utils import paths
from envsyncer.utils.errors import VaultError
from envsyncer.utils.logging import get_logger

_log = get_logger()

_ACTION_STYLE = {
    SyncAction.IN_SYNC: "[dim]in sync[/]",
    SyncAction.UPLOAD: "[green]upload ↑[/]",
    SyncAction.DOWNLOAD: "[blue]download ↓[/]",
    SyncAction.CONFLICT: "[yellow]conflict ![/]",
}


class LocalScan(NamedTuple):
    """What the working tree holds: files to sync, plus the ones held back."""

    files: dict[str, SecretFile]
    excluded: frozenset[str]


# -- indices --------------------------------------------------------------
def scan_local(session: Session, remote: dict[str, RemoteFile] | None = None) -> LocalScan:
    """Index the local secrets, adopting anything the vault already tracks.

    Pattern matching alone is not enough: the moment the pattern list changes
    (or differs between two machines) a tracked file would drop out of the scan
    and look like it only existed on the remote, which is how a fresh local file
    ends up being offered for overwrite by a stale vault copy.
    """
    assert session.root is not None
    secrets = discover_secrets(
        session.root,
        extra_includes=session.config.include_patterns(),
        extra_excludes=session.config.exclude_patterns(),
    )
    files = {sf.relative_path: sf for sf in secrets}

    if not remote:
        return LocalScan(files, frozenset())

    adopted, excluded = adopt_tracked(
        session.root,
        [rel for rel in remote if rel not in files],
        extra_excludes=session.config.exclude_patterns(),
    )
    files.update(adopted)
    return LocalScan(files, frozenset(excluded))


def remote_index(session: Session, profile: str) -> dict[str, RemoteFile]:
    return session.vault.read_profile_metadata(session.project_key, profile)


def _as_remote(local: SecretFile) -> RemoteFile:
    return RemoteFile(local.relative_path, local.sha256, local.size)


def _destination(session: Session, relative_path: str) -> Path:
    assert session.root is not None
    try:
        return paths.safe_join(session.root, relative_path)
    except ValueError as exc:
        raise VaultError(str(exc)) from exc


def _write_secret(destination: Path, content: bytes) -> None:
    """Write a downloaded secret owner-readable only."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    try:
        os.chmod(destination, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


# -- presentation ---------------------------------------------------------
def render_plan(plan: SyncPlan) -> None:
    table = Table(title=f"Sync plan — profile '{plan.profile}'", title_style="bold")
    table.add_column("Action")
    table.add_column("File")
    table.add_column("Note", style="dim")
    for fp in plan.files:
        table.add_row(_ACTION_STYLE[fp.action], fp.relative_path, fp.reason)
    console.print(table)


def render_hints(plan: SyncPlan) -> None:
    """Point at the commands that resolve whatever the plan is showing."""
    vault_only = [fp for fp in plan.files if fp.action is SyncAction.DOWNLOAD and fp.local is None]
    if vault_only:
        plain(
            f"[dim]{len(vault_only)} file(s) are in the vault but not in this project. "
            "Run [/][bold]envsyncer[/][dim] to download them, or "
            "[/][bold]envsyncer delete <path>[/][dim] to remove them from the vault.[/]"
        )
    if plan.of(SyncAction.CONFLICT):
        plain("[dim]Conflicts are resolved one by one when you run [/][bold]envsyncer[/][dim].[/]")


# -- sync -----------------------------------------------------------------
def run_sync(session: Session, profile: str) -> None:
    remote = remote_index(session, profile)
    scan = scan_local(session, remote)
    baseline = cache.load_baseline(session.project_key, profile)
    plan = build_plan(profile, scan.files, remote, baseline, excluded=scan.excluded)

    if not plan.files:
        info("No secret files found locally or in the vault for this profile.")
        return

    render_plan(plan)
    if not plan.has_changes:
        # Identical on both sides is a perfectly good baseline; recording it now
        # keeps the next one-sided edit from being reported as a conflict.
        cache.save_baseline(
            session.project_key,
            profile,
            {fp.relative_path: fp.local.sha256 for fp in plan.files if fp.local},
        )
        success("Everything is in sync.")
        return

    final_remote = dict(remote)
    new_baseline = dict(baseline)
    uploaded_count = 0
    deleted_count = 0

    for fp in plan.files:
        rel = fp.relative_path

        if fp.action is SyncAction.IN_SYNC:
            assert fp.local is not None
            new_baseline[rel] = fp.local.sha256

        elif fp.action is SyncAction.UPLOAD:
            if _do_upload(session, profile, fp):
                final_remote[rel] = _as_remote(fp.local)  # type: ignore[arg-type]
                new_baseline[rel] = fp.local.sha256  # type: ignore[union-attr]
                uploaded_count += 1

        elif fp.action is SyncAction.DOWNLOAD and fp.local is None:
            outcome = _resolve_vault_only(session, profile, fp, excluded=rel in scan.excluded)
            if outcome == "downloaded":
                final_remote[rel] = fp.remote  # type: ignore[assignment]
                new_baseline[rel] = fp.remote.sha256  # type: ignore[union-attr]
            elif outcome == "deleted":
                final_remote.pop(rel, None)
                new_baseline.pop(rel, None)
                deleted_count += 1

        elif fp.action is SyncAction.DOWNLOAD:
            if _do_download(session, profile, fp):
                final_remote[rel] = fp.remote  # type: ignore[assignment]
                new_baseline[rel] = fp.remote.sha256  # type: ignore[union-attr]

        elif fp.action is SyncAction.CONFLICT:
            outcome = _resolve_conflict(session, profile, fp, scan.files, new_baseline)
            if outcome == "stop":
                return
            if outcome == "uploaded":
                final_remote[rel] = _as_remote(fp.local)  # type: ignore[arg-type]
                uploaded_count += 1
            elif outcome == "downloaded":
                final_remote[rel] = fp.remote  # type: ignore[assignment]

    # Only uploads and deletions change the vault, so only they warrant a
    # commit. A download-only sync updates local files (and the local baseline)
    # but must not create a spurious vault commit.
    if session.vault.has_staged():
        session.vault.stage_profile_metadata(session.project_key, profile, final_remote)
        session.vault.stage_manifest(session.project_key, profile)
        session.vault.commit(
            f"envsyncer: sync {session.project_key}/{profile} "
            f"({uploaded_count} uploaded, {deleted_count} deleted)"
        )
    cache.save_baseline(session.project_key, profile, new_baseline)
    success("Sync complete.")


def _do_upload(session: Session, profile: str, fp: FilePlan) -> bool:
    assert fp.local is not None
    if not prompts.confirm(f"Upload {fp.relative_path}?", assume_yes=session.assume_yes):
        return False
    content = fp.local.absolute_path.read_bytes()
    session.vault.stage_file(session.project_key, profile, fp.relative_path, content)
    uploaded(fp.relative_path)
    _log.info("upload project=%s profile=%s path=%s", session.project_key, profile, fp.relative_path)
    return True


def _do_download(session: Session, profile: str, fp: FilePlan) -> bool:
    if not prompts.confirm(f"Download {fp.relative_path}?", assume_yes=session.assume_yes):
        return False
    _fetch_into_project(session, profile, fp.relative_path)
    return True


def _fetch_into_project(session: Session, profile: str, relative_path: str) -> None:
    content = session.vault.download(session.project_key, profile, relative_path)
    _write_secret(_destination(session, relative_path), content)
    downloaded(relative_path)
    _log.info("download project=%s profile=%s path=%s", session.project_key, profile, relative_path)


def _delete_from_vault(session: Session, profile: str, relative_path: str) -> None:
    session.vault.stage_delete(session.project_key, profile, relative_path)
    removed(f"{relative_path} (removed from the vault)")
    _log.info("delete project=%s profile=%s path=%s", session.project_key, profile, relative_path)


def _resolve_vault_only(session: Session, profile: str, fp: FilePlan, *, excluded: bool) -> str:
    """A file is in the vault but not in the project: download it, or drop it.

    Return one of: 'downloaded', 'deleted', 'skipped'.
    """
    rel = fp.relative_path

    if excluded:
        warn(f"{rel} is excluded on this machine but still stored in the vault.")
        if session.assume_yes:
            info("Left alone. Run `envsyncer delete` to remove it from the vault.")
            return "skipped"
    elif session.assume_yes:
        return "downloaded" if _do_download(session, profile, fp) else "skipped"

    choice = prompts.select(
        f"'{rel}' is in the vault but not in this project",
        [
            "Download it into this project",
            "Delete it from the vault (your local files are untouched)",
            "Skip for now",
        ],
        default_index=1 if excluded else 0,
    )

    if choice == 0:
        _fetch_into_project(session, profile, rel)
        return "downloaded"

    if choice == 1:
        if not prompts.confirm(
            f"Permanently delete {rel} from vault profile '{profile}'?", default=False
        ):
            info("Left in the vault.")
            return "skipped"
        _delete_from_vault(session, profile, rel)
        return "deleted"

    return "skipped"


def _resolve_conflict(
    session: Session,
    profile: str,
    fp: FilePlan,
    local: dict[str, SecretFile],
    new_baseline: dict[str, str],
) -> str:
    """Return one of: 'uploaded', 'downloaded', 'skipped', 'stop'."""
    remote_bytes = session.vault.download(session.project_key, profile, fp.relative_path)
    decision = conflict.resolve(fp, remote_bytes, assume_yes=session.assume_yes)
    _log.info("conflict project=%s profile=%s path=%s decision=%s",
              session.project_key, profile, fp.relative_path, decision.value)

    if decision is ConflictDecision.SKIP:
        return "skipped"

    if decision is ConflictDecision.UPLOAD:
        content = fp.local.absolute_path.read_bytes()  # type: ignore[union-attr]
        session.vault.stage_file(session.project_key, profile, fp.relative_path, content)
        uploaded(fp.relative_path)
        new_baseline[fp.relative_path] = fp.local.sha256  # type: ignore[union-attr]
        return "uploaded"

    if decision is ConflictDecision.DOWNLOAD:
        _write_secret(_destination(session, fp.relative_path), remote_bytes)
        downloaded(fp.relative_path)
        new_baseline[fp.relative_path] = fp.remote.sha256  # type: ignore[union-attr]
        return "downloaded"

    # NEW_PROFILE — preserve all local work under a fresh profile and switch to it.
    _save_local_as_new_profile(session, local)
    return "stop"


def _save_local_as_new_profile(session: Session, local: dict[str, SecretFile]) -> None:
    name = prompts.ask_text("New profile name", default=SUGGESTED_NEW_PROFILE).strip() or SUGGESTED_NEW_PROFILE
    info(f"Saving your local secrets to new profile [bold]{name}[/] …")
    new_remote: dict[str, RemoteFile] = {}
    for rel, sf in local.items():
        session.vault.stage_file(session.project_key, name, rel, sf.absolute_path.read_bytes())
        uploaded(f"{name}/{rel}")
        new_remote[rel] = _as_remote(sf)
    session.vault.stage_profile_metadata(session.project_key, name, new_remote)
    session.vault.stage_manifest(session.project_key, name)
    session.vault.commit(f"envsyncer: save local as profile {session.project_key}/{name}")
    session.config.set_profile(session.project_key, name)
    session.config.save()
    cache.save_baseline(session.project_key, name, {rel: sf.sha256 for rel, sf in local.items()})
    success(f"Local secrets saved as profile '{name}', now your active profile. Re-run to continue.")


# -- one-directional (push / pull) ----------------------------------------
def run_push(session: Session, profile: str) -> None:
    remote = remote_index(session, profile)
    local = scan_local(session, remote).files
    if not local:
        warn("No local secret files found to push.")
        return
    if not prompts.confirm(
        f"Push {len(local)} local file(s) to profile '{profile}' (overwrites remote)?",
        assume_yes=session.assume_yes,
    ):
        info("Cancelled.")
        return

    final_remote: dict[str, RemoteFile] = {}
    for rel, sf in local.items():
        session.vault.stage_file(session.project_key, profile, rel, sf.absolute_path.read_bytes())
        uploaded(rel)
        final_remote[rel] = _as_remote(sf)

    # Files the vault still holds that this machine no longer has. Dropping them
    # from the metadata without deleting them would leave unreachable blobs, so
    # it is either a real delete or they stay listed.
    for rel in sorted(set(remote) - set(local)):
        if _push_should_delete(session, rel):
            _delete_from_vault(session, profile, rel)
        else:
            final_remote[rel] = remote[rel]

    session.vault.stage_profile_metadata(session.project_key, profile, final_remote)
    session.vault.stage_manifest(session.project_key, profile)
    session.vault.commit(f"envsyncer: push {session.project_key}/{profile} ({len(local)} files)")
    cache.save_baseline(
        session.project_key, profile, {rel: rf.sha256 for rel, rf in final_remote.items()}
    )
    success(f"Pushed {len(local)} file(s) to '{profile}'.")


def _push_should_delete(session: Session, relative_path: str) -> bool:
    if session.assume_yes:
        warn(f"{relative_path} is in the vault but not here — left in place.")
        return False
    return prompts.confirm(
        f"{relative_path} is in the vault but not in this project. Delete it from the vault?",
        default=False,
    )


def run_pull(session: Session, profile: str) -> None:
    remote = remote_index(session, profile)
    if not remote:
        warn(f"Profile '{profile}' has no files in the vault to pull.")
        return
    if not prompts.confirm(
        f"Pull {len(remote)} file(s) from profile '{profile}' (overwrites local)?",
        assume_yes=session.assume_yes,
    ):
        info("Cancelled.")
        return
    new_baseline: dict[str, str] = {}
    for rel, rf in remote.items():
        _fetch_into_project(session, profile, rel)
        new_baseline[rel] = rf.sha256
    cache.save_baseline(session.project_key, profile, new_baseline)
    success(f"Pulled {len(remote)} file(s) from '{profile}'.")


# -- delete ----------------------------------------------------------------
def run_delete(session: Session, profile: str, targets: list[str]) -> None:
    """Remove ``targets`` from the vault profile; local copies are untouched."""
    remote = remote_index(session, profile)
    final_remote = {rel: rf for rel, rf in remote.items() if rel not in targets}
    for rel in targets:
        _delete_from_vault(session, profile, rel)

    session.vault.stage_profile_metadata(session.project_key, profile, final_remote)
    session.vault.stage_manifest(session.project_key, profile)
    session.vault.commit(
        f"envsyncer: delete {len(targets)} file(s) from {session.project_key}/{profile}"
    )

    baseline = cache.load_baseline(session.project_key, profile)
    for rel in targets:
        baseline.pop(rel, None)
    cache.save_baseline(session.project_key, profile, baseline)
    success(f"Deleted {len(targets)} file(s) from '{profile}'. Local copies are untouched.")
