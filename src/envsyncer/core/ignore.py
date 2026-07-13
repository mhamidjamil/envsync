"""Ignore rules for repository scanning.

Combines a fixed set of always-skip directories with any user-supplied
``.envsyncignore`` file (gitignore syntax, matched via `pathspec`).
"""

from __future__ import annotations

from pathlib import Path

import pathspec

#: Directories never worth scanning for secrets. Pruned during the walk so we
#: don't descend into huge trees like ``node_modules``.
DEFAULT_IGNORED_DIRS: frozenset[str] = frozenset(
    {".git", "node_modules", "vendor", "build", "dist", ".next"}
)

IGNORE_FILENAME = ".envsyncignore"


class IgnoreMatcher:
    """Decides whether a path (relative to the repo root) should be skipped."""

    def __init__(self, spec: pathspec.PathSpec | None) -> None:
        self._spec = spec

    @classmethod
    def load(cls, repo_root: Path) -> "IgnoreMatcher":
        """Build a matcher from ``<repo_root>/.envsyncignore`` if present."""
        ignore_file = repo_root / IGNORE_FILENAME
        if not ignore_file.is_file():
            return cls(None)
        lines = ignore_file.read_text(encoding="utf-8").splitlines()
        return cls(pathspec.PathSpec.from_lines("gitignore", lines))

    def is_dir_ignored(self, name: str, relative_path: str) -> bool:
        """True if a directory should be pruned from the walk."""
        if name in DEFAULT_IGNORED_DIRS:
            return True
        # pathspec expects a trailing slash to reliably match directory rules.
        return self._matches(relative_path.rstrip("/") + "/")

    def is_file_ignored(self, relative_path: str) -> bool:
        """True if a file should be excluded from discovery."""
        return self._matches(relative_path)

    def _matches(self, relative_path: str) -> bool:
        return bool(self._spec and self._spec.match_file(relative_path))
