"""Shared building blocks for the sync/status/push/pull commands."""

from __future__ import annotations

from rich.table import Table

from envsyncer.commands import conflict
from envsyncer.commands.conflict import ConflictDecision
from envsyncer.core import cache
from envsyncer.core.discovery import discover_secrets
from envsyncer.core.profiles import SUGGESTED_NEW_PROFILE
from envsyncer.core.session import Session
from envsyncer.core.sync_engine import build_plan
from envsyncer.models import FilePlan, RemoteFile, SecretFile, SyncAction, SyncPlan
from envsyncer.ui import prompts
from envsyncer.ui.console import console, downloaded, info, success, uploaded, warn
from envsyncer.utils.logging import get_logger

_log = get_logger()

_ACTION_STYLE = {
    SyncAction.IN_SYNC: "[dim]in sync[/]",
    SyncAction.UPLOAD: "[green]upload ↑[/]",
    SyncAction.DOWNLOAD: "[blue]download ↓[/]",
    SyncAction.CONFLICT: "[yellow]conflict ![/]",
}


# -- indices --------------------------------------------------------------
def local_index(session: Session) -> dict[str, SecretFile]:
    assert session.root is not None
    secrets = discover_secrets(
        session.root,
        extra_includes=session.config.include_patterns(),
        extra_excludes=session.config.exclude_patterns(),
    )
    return {sf.relative_path: sf for sf in secrets}


def remote_index(session: Session, profile: str) -> dict[str, RemoteFile]:
    return session.vault.read_profile_metadata(session.project_key, profile)


def _as_remote(local: SecretFile) -> RemoteFile:
    return RemoteFile(local.relative_path, local.sha256, local.size)


# -- presentation ---------------------------------------------------------
def render_plan(plan: SyncPlan) -> None:
    table = Table(title=f"Sync plan — profile '{plan.profile}'", title_style="bold")
    table.add_column("Action")
    table.add_column("File")
    table.add_column("Note", style="dim")
    for fp in plan.files:
        table.add_row(_ACTION_STYLE[fp.action], fp.relative_path, fp.reason)
    console.print(table)


# -- sync -----------------------------------------------------------------
def run_sync(session: Session, profile: str) -> None:
    local = local_index(session)
    remote = remote_index(session, profile)
    baseline = cache.load_baseline(session.project_key, profile)
    plan = build_plan(profile, local, remote, baseline)

    if not plan.files:
        info("No secret files found locally or in the vault for this profile.")
        return

    render_plan(plan)
    if not plan.has_changes:
        success("Everything is in sync.")
        return

    final_remote = dict(remote)
    new_baseline = dict(baseline)
    uploaded_count = 0

    for fp in plan.files:
        if fp.action is SyncAction.IN_SYNC:
            assert fp.local is not None
            new_baseline[fp.relative_path] = fp.local.sha256

        elif fp.action is SyncAction.UPLOAD:
            if _do_upload(session, profile, fp):
                final_remote[fp.relative_path] = _as_remote(fp.local)  # type: ignore[arg-type]
                new_baseline[fp.relative_path] = fp.local.sha256  # type: ignore[union-attr]
                uploaded_count += 1

        elif fp.action is SyncAction.DOWNLOAD:
            if _do_download(session, profile, fp):
                final_remote[fp.relative_path] = fp.remote  # type: ignore[assignment]
                new_baseline[fp.relative_path] = fp.remote.sha256  # type: ignore[union-attr]

        elif fp.action is SyncAction.CONFLICT:
            outcome = _resolve_conflict(session, profile, fp, local, new_baseline)
            if outcome == "stop":
                return
            if outcome == "uploaded":
                final_remote[fp.relative_path] = _as_remote(fp.local)  # type: ignore[arg-type]
                uploaded_count += 1
            elif outcome == "downloaded":
                final_remote[fp.relative_path] = fp.remote  # type: ignore[assignment]

    # Only uploads change the vault, so only they warrant a commit. A
    # download-only sync updates local files (and the local baseline) but must
    # not create a spurious vault commit.
    if uploaded_count > 0:
        session.vault.stage_profile_metadata(session.project_key, profile, final_remote)
        session.vault.stage_manifest(session.project_key, profile)
        session.vault.commit(
            f"envsyncer: sync {session.project_key}/{profile} ({uploaded_count} file(s))"
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
    assert fp.remote is not None and session.root is not None
    if not prompts.confirm(f"Download {fp.relative_path}?", assume_yes=session.assume_yes):
        return False
    content = session.vault.download(session.project_key, profile, fp.relative_path)
    dest = session.root / fp.relative_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    downloaded(fp.relative_path)
    _log.info("download project=%s profile=%s path=%s", session.project_key, profile, fp.relative_path)
    return True


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
        assert session.root is not None
        dest = session.root / fp.relative_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(remote_bytes)
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
    local = local_index(session)
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
    session.vault.stage_profile_metadata(session.project_key, profile, final_remote)
    session.vault.stage_manifest(session.project_key, profile)
    session.vault.commit(f"envsyncer: push {session.project_key}/{profile} ({len(local)} files)")
    cache.save_baseline(session.project_key, profile, {rel: sf.sha256 for rel, sf in local.items()})
    success(f"Pushed {len(local)} file(s) to '{profile}'.")


def run_pull(session: Session, profile: str) -> None:
    assert session.root is not None
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
        content = session.vault.download(session.project_key, profile, rel)
        dest = session.root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        downloaded(rel)
        new_baseline[rel] = rf.sha256
    cache.save_baseline(session.project_key, profile, new_baseline)
    success(f"Pulled {len(remote)} file(s) from '{profile}'.")
