"""Detect the current git repository and derive its ``owner/repo`` identity.

Supports both SSH and HTTPS remotes. The git root (the directory containing
``.git``) is the anchor for every relative path, so running ``envsyncer`` from
any subdirectory behaves identically.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from envsyncer.models import RepoIdentity
from envsyncer.utils.errors import LocalRepoError

# git@github.com:owner/repo(.git)      https://github.com/owner/repo(.git)
# ssh://git@github.com/owner/repo(.git)
_REMOTE_RE = re.compile(
    r"""
    (?:git@[^:]+:|https?://[^/]+/|ssh://[^/]+/)  # scheme / host
    (?P<owner>[^/]+)/
    (?P<name>[^/]+?)
    (?:\.git)?/?$
    """,
    re.VERBOSE,
)


def _run_git(args: list[str], cwd: Path | None = None) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:  # git not installed
        raise LocalRepoError("git is not installed or not on PATH.") from exc
    except subprocess.CalledProcessError as exc:
        raise LocalRepoError((exc.stderr or "git command failed").strip()) from exc
    return result.stdout.strip()


def find_git_root(start: Path | None = None) -> Path:
    """Return the repository root, or raise if we are not inside one."""
    cwd = start or Path.cwd()
    try:
        root = _run_git(["rev-parse", "--show-toplevel"], cwd=cwd)
    except LocalRepoError as exc:
        raise LocalRepoError(
            "Not inside a git repository. Run EnvSyncer from within a project."
        ) from exc
    return Path(root)


def parse_remote(url: str) -> RepoIdentity:
    """Parse an SSH or HTTPS git remote URL into a :class:`RepoIdentity`."""
    match = _REMOTE_RE.search(url.strip())
    if not match:
        raise LocalRepoError(f"Could not parse owner/repo from remote URL: {url!r}")
    return RepoIdentity(owner=match.group("owner"), name=match.group("name"))


def detect_repo(start: Path | None = None) -> tuple[RepoIdentity, Path]:
    """Return ``(identity, git_root)`` for the repository at ``start``."""
    root = find_git_root(start)
    try:
        remote = _run_git(["remote", "get-url", "origin"], cwd=root)
    except LocalRepoError as exc:
        raise LocalRepoError(
            "This repository has no 'origin' remote, so it can't be identified. "
            "Add one with `git remote add origin <url>`."
        ) from exc
    return parse_remote(remote), root
