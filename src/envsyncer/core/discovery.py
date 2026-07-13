"""Recursively discover secret files in the local working tree.

The set of "what counts as a secret" is a single, easily extended registry
(:data:`DEFAULT_SECRET_PATTERNS`). To support a new file type, add a pattern —
nothing else in the codebase needs to change.
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path, PurePosixPath

from envsyncer.core.hashing import sha256_file
from envsyncer.core.ignore import IgnoreMatcher
from envsyncer.models import SecretFile

#: Glob patterns (matched against the *file name*) that mark a file as a secret.
DEFAULT_SECRET_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "arduino_secrets.h",
    "firebase.json",
    "service-account.json",
)


def _is_secret_name(name: str) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in DEFAULT_SECRET_PATTERNS)


def discover_secrets(repo_root: Path) -> list[SecretFile]:
    """Walk ``repo_root`` and return every secret file, hashed.

    Relative paths are POSIX-style (forward slashes) so the vault layout is
    identical no matter which OS created it.
    """
    matcher = IgnoreMatcher.load(repo_root)
    found: list[SecretFile] = []

    for dirpath, dirnames, filenames in os.walk(repo_root):
        current = Path(dirpath)

        # Prune ignored directories in-place so os.walk skips descending them.
        kept: list[str] = []
        for dirname in dirnames:
            rel = PurePosixPath((current / dirname).relative_to(repo_root).as_posix())
            if not matcher.is_dir_ignored(dirname, str(rel)):
                kept.append(dirname)
        dirnames[:] = kept

        for filename in filenames:
            if not _is_secret_name(filename):
                continue
            abs_path = current / filename
            rel = (abs_path).relative_to(repo_root).as_posix()
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
