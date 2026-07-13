"""Shared domain types passed between modules.

Keeping these as small dataclasses/enums (rather than loose dicts) gives every
module the same vocabulary and makes the sync engine trivially unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class SyncAction(str, Enum):
    """What should happen to a single file during a sync."""

    IN_SYNC = "in-sync"        # local and remote are byte-identical
    UPLOAD = "upload"          # push local -> vault
    DOWNLOAD = "download"      # pull vault -> local
    CONFLICT = "conflict"      # both sides diverged from the last-synced baseline


@dataclass(frozen=True)
class RepoIdentity:
    """Identifies a project by ``owner/repository``.

    This is derived from the project's git remote and is used purely as the
    *logical key* (a folder path) inside the vault. It is independent of who
    owns the vault repository itself.
    """

    owner: str
    name: str

    @property
    def key(self) -> str:
        return f"{self.owner}/{self.name}"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.key


@dataclass(frozen=True)
class SecretFile:
    """A secret file discovered in the local working tree."""

    relative_path: str   # POSIX-style path relative to the git root, e.g. "secret/.env"
    absolute_path: Path
    sha256: str
    size: int


@dataclass(frozen=True)
class RemoteFile:
    """A secret file recorded in a profile's vault metadata."""

    relative_path: str
    sha256: str
    size: int


@dataclass
class FilePlan:
    """The decision for a single relative path within a sync."""

    relative_path: str
    action: SyncAction
    local: SecretFile | None = None
    remote: RemoteFile | None = None
    reason: str = ""


@dataclass
class SyncPlan:
    """The full set of per-file decisions for one sync run."""

    profile: str
    files: list[FilePlan] = field(default_factory=list)

    def of(self, action: SyncAction) -> list[FilePlan]:
        return [f for f in self.files if f.action == action]

    @property
    def has_changes(self) -> bool:
        return any(f.action is not SyncAction.IN_SYNC for f in self.files)
