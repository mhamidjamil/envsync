"""Recursively discover secret files in the local working tree.

The set of "what counts as a secret" is a single, easily extended registry
(:data:`DEFAULT_SECRET_PATTERNS`). To support a new file type, add a pattern —
nothing else in the codebase needs to change.

Patterns are matched by bare file name *or* by repository-relative path, so
``local.properties``, ``android/local.properties`` and a full absolute path all
work. A file already recorded in the vault is adopted even when no pattern
matches it (:func:`adopt_tracked`), because being in the vault is itself proof
the project syncs it.
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path, PurePosixPath
from typing import Iterable

import pathspec

from envsyncer.core.hashing import sha256_file
from envsyncer.core.ignore import IgnoreMatcher
from envsyncer.models import SecretFile

#: Glob patterns (matched against the *file name*) that mark a file as a secret.
DEFAULT_SECRET_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "arduino_secrets.h",
    "secrets.h",
    "firebase.json",
    "service-account.json",
)

#: Glob patterns that, when matched, EXCLUDE a file even if it looked like a
#: secret. These are templates/samples that are safe to keep in version control
#: and should never be synced (e.g. ``.env.example``, ``config.sample``).
DEFAULT_EXCLUDE_PATTERNS: tuple[str, ...] = (
    "*.example",
    "*.sample",
    "*.template",
)


def _normalise(pattern: str, repo_root: Path) -> str | None:
    """Reduce a user pattern to a name glob or a repo-relative path glob.

    An absolute path is accepted (people paste them straight from the shell)
    and becomes a path rule relative to ``repo_root``; one that points outside
    this project can never match here, so it is dropped.
    """
    text = pattern.strip().replace("\\", "/")
    if not text:
        return None
    if text.startswith("~"):
        text = Path(text).expanduser().as_posix()
    if os.path.isabs(text):
        try:
            text = Path(text).resolve().relative_to(repo_root).as_posix()
        except ValueError:
            return None
    if text.startswith("./"):
        text = text[2:]
    return text or None


class PatternSet:
    """Matches a file by bare name or by repository-relative path.

    A pattern without a slash is a name glob and matches anywhere in the tree
    (``*.pem``). A pattern with a slash is a gitignore-style path rule
    (``android/local.properties``, ``config/**``).
    """

    def __init__(self, patterns: Iterable[str], repo_root: Path) -> None:
        names: list[str] = []
        paths: list[str] = []
        for raw in patterns:
            normalised = _normalise(raw, repo_root)
            if normalised is None:
                continue
            (paths if "/" in normalised else names).append(normalised)
        self._names = tuple(names)
        self._spec = pathspec.PathSpec.from_lines("gitignore", paths) if paths else None

    def __bool__(self) -> bool:
        return bool(self._names or self._spec)

    def matches(self, name: str, relative_path: str) -> bool:
        if any(fnmatch.fnmatch(name, pattern) for pattern in self._names):
            return True
        return bool(self._spec and self._spec.match_file(relative_path))


def discover_secrets(
    repo_root: Path,
    *,
    extra_includes: tuple[str, ...] = (),
    extra_excludes: tuple[str, ...] = (),
) -> list[SecretFile]:
    """Walk ``repo_root`` and return every secret file, hashed.

    A file is included when it matches an include pattern (defaults plus any
    ``extra_includes``) AND does not match an exclude pattern (defaults plus any
    ``extra_excludes``). Relative paths are POSIX-style (forward slashes) so the
    vault layout is identical no matter which OS created it.
    """
    repo_root = repo_root.resolve()
    includes = PatternSet((*DEFAULT_SECRET_PATTERNS, *extra_includes), repo_root)
    excludes = PatternSet((*DEFAULT_EXCLUDE_PATTERNS, *extra_excludes), repo_root)
    matcher = IgnoreMatcher.load(repo_root)
    found: list[SecretFile] = []

    for dirpath, dirnames, filenames in os.walk(repo_root):
        current = Path(dirpath)

        # Prune ignored directories in-place so os.walk skips descending them.
        kept: list[str] = []
        for dirname in dirnames:
            rel = PurePosixPath((current / dirname).relative_to(repo_root).as_posix())
            if matcher.is_dir_ignored(dirname, str(rel)):
                continue
            # A nested repository or git worktree (e.g. .claude/worktrees/*) has
            # its own secrets and its own vault entry — never scoop them in here.
            if (current / dirname / ".git").exists():
                continue
            kept.append(dirname)
        dirnames[:] = kept

        for filename in filenames:
            abs_path = current / filename
            rel = abs_path.relative_to(repo_root).as_posix()
            if not includes.matches(filename, rel):
                continue
            if excludes.matches(filename, rel):
                continue
            if matcher.is_file_ignored(rel):
                continue
            found.append(
                SecretFile(
                    relative_path=rel,
                    absolute_path=abs_path,
                    sha256=sha256_file(abs_path),
                    size=abs_path.stat().st_size,
                )
            )

    found.sort(key=lambda secret: secret.relative_path)
    return found


def adopt_tracked(
    repo_root: Path,
    tracked: Iterable[str],
    *,
    extra_excludes: tuple[str, ...] = (),
) -> tuple[dict[str, SecretFile], set[str]]:
    """Hash vault-tracked files that exist on disk but matched no pattern.

    Returns ``(adopted, excluded)``. A file recorded in the profile is one this
    project already syncs, so a pattern list that has drifted — or that differs
    between two machines — must never make a file that is sitting right there
    look like it only exists on the remote. The one exception is a file the user
    explicitly excluded (``envsyncer exclude`` or ``.envsyncignore``): that is a
    deliberate local decision, so it is reported back instead of adopted.
    """
    repo_root = repo_root.resolve()
    excludes = PatternSet(extra_excludes, repo_root)
    matcher = IgnoreMatcher.load(repo_root)
    adopted: dict[str, SecretFile] = {}
    excluded: set[str] = set()

    for rel in tracked:
        abs_path = repo_root / rel
        try:
            abs_path.resolve().relative_to(repo_root)
        except ValueError:
            continue  # vault path escapes the project — ignore it entirely
        if not abs_path.is_file():
            continue
        name = PurePosixPath(rel).name
        if excludes.matches(name, rel) or matcher.is_file_ignored(rel):
            excluded.add(rel)
            continue
        adopted[rel] = SecretFile(
            relative_path=rel,
            absolute_path=abs_path,
            sha256=sha256_file(abs_path),
            size=abs_path.stat().st_size,
        )

    return adopted, excluded
