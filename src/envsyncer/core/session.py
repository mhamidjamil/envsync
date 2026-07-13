"""Bootstraps everything a command needs: config, client, vault, repo, root.

Commands call :func:`open_session` and receive a ready-to-use :class:`Session`.
This is where "run setup if needed" and "detect the git repo" happen once, so
each command stays focused on its own behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from envsyncer.core.config import Config
from envsyncer.core.github_client import GitHubClient
from envsyncer.core.local_repo import detect_repo
from envsyncer.core.setup import ensure_setup
from envsyncer.core.vault import VaultManager
from envsyncer.models import RepoIdentity


@dataclass
class Session:
    config: Config
    client: GitHubClient
    vault: VaultManager
    assume_yes: bool
    repo: RepoIdentity | None = None
    root: Path | None = None

    @property
    def project_key(self) -> str:
        assert self.repo is not None
        return self.repo.key


def open_session(*, assume_yes: bool = False, need_repo: bool = True) -> Session:
    """Prepare a session, running first-run setup and (optionally) repo detection."""
    config = ensure_setup(assume_yes=assume_yes)
    client = GitHubClient(config.github_token)
    vault = VaultManager(client, config)

    repo = root = None
    if need_repo:
        repo, root = detect_repo()

    return Session(
        config=config,
        client=client,
        vault=vault,
        assume_yes=assume_yes,
        repo=repo,
        root=root,
    )
