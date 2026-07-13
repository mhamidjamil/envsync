"""Interactive conflict resolution (both sides changed since the last sync)."""

from __future__ import annotations

import difflib
from enum import Enum

from envsyncer.models import FilePlan
from envsyncer.ui import prompts
from envsyncer.ui.console import console, plain, warn


class ConflictDecision(str, Enum):
    DOWNLOAD = "download"        # replace local with remote
    UPLOAD = "upload"            # replace remote with local
    NEW_PROFILE = "new-profile"  # save local as a new profile
    SKIP = "skip"                # leave untouched


def resolve(plan_file: FilePlan, remote_bytes: bytes, *, assume_yes: bool) -> ConflictDecision:
    """Prompt for how to resolve one conflicted file.

    Under ``--yes`` we never guess a destructive action — the file is skipped.
    """
    if assume_yes:
        warn(f"Conflict on {plan_file.relative_path} — skipped (non-interactive).")
        return ConflictDecision.SKIP

    warn(f"Conflict detected: [bold]{plan_file.relative_path}[/]")
    options = [
        "Show differences",
        "Replace local with remote",
        "Replace remote with local",
        "Save local as a new profile",
        "Cancel (leave unchanged)",
    ]
    while True:
        choice = prompts.select("Resolve", options, default_index=4)
        if choice == 0:
            _show_diff(plan_file, remote_bytes)
            continue
        return {
            1: ConflictDecision.DOWNLOAD,
            2: ConflictDecision.UPLOAD,
            3: ConflictDecision.NEW_PROFILE,
            4: ConflictDecision.SKIP,
        }[choice]


def _show_diff(plan_file: FilePlan, remote_bytes: bytes) -> None:
    assert plan_file.local is not None
    try:
        local_text = plan_file.local.absolute_path.read_text(encoding="utf-8").splitlines()
        remote_text = remote_bytes.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        warn("Binary file — cannot show a textual diff.")
        return

    diff = difflib.unified_diff(
        remote_text, local_text,
        fromfile=f"remote/{plan_file.relative_path}",
        tofile=f"local/{plan_file.relative_path}",
        lineterm="",
    )
    plain("")
    any_line = False
    for line in diff:
        any_line = True
        if line.startswith("+") and not line.startswith("+++"):
            console.print(f"[green]{line}[/]")
        elif line.startswith("-") and not line.startswith("---"):
            console.print(f"[red]{line}[/]")
        elif line.startswith("@@"):
            console.print(f"[cyan]{line}[/]")
        else:
            console.print(f"[dim]{line}[/]")
    if not any_line:
        plain("[dim](no textual differences)[/]")
    plain("")
