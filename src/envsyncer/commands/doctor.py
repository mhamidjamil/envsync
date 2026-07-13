"""`envsyncer doctor` — diagnose configuration and connectivity.

Read-only and non-interactive: it never triggers setup or prompts. Each check
prints a pass/fail line so a user (or a bug report) can see exactly what's wrong.
"""

from __future__ import annotations

import os
import stat

from envsyncer.core.config import Config
from envsyncer.core.github_client import GitHubClient
from envsyncer.core.local_repo import detect_repo
from envsyncer.ui.console import error, info, success, warn
from envsyncer.utils import paths
from envsyncer.utils.errors import EnvSyncerError


def run(assume_yes: bool = False) -> None:  # noqa: ARG001 - uniform command signature
    info("Running EnvSyncer diagnostics…\n")
    config = Config.load()

    _check_config_file()
    client = _check_token(config)
    if client is not None:
        _check_vault(config, client)
    _check_repo()


def _check_config_file() -> None:
    if not paths.CONFIG_FILE.exists():
        warn(f"No config yet at {paths.CONFIG_FILE} — run `envsyncer setup`.")
        return
    success(f"Config file present: {paths.CONFIG_FILE}")
    try:
        mode = stat.S_IMODE(os.stat(paths.CONFIG_FILE).st_mode)
        if mode & (stat.S_IRWXG | stat.S_IRWXO):
            warn("Config is group/world-accessible; expected 0600 (owner-only).")
        else:
            success("Config permissions are owner-only (0600).")
    except OSError:
        pass


def _check_token(config: Config) -> GitHubClient | None:
    if not config.has_token():
        error("No GitHub token configured — run `envsyncer setup`.")
        return None
    client = GitHubClient(config.github_token)
    try:
        user = client.get_authenticated_user()
    except EnvSyncerError as exc:
        error(f"Token check failed: {exc}")
        return None
    success(f"Token valid — authenticated as {user}.")
    return client


def _check_vault(config: Config, client: GitHubClient) -> None:
    owner = config.github_user
    repo = config.vault_repo
    try:
        data = client.get_repo(owner, repo)
    except EnvSyncerError as exc:
        error(f"Vault check failed: {exc}")
        return
    if data is None:
        error(f"Vault repository {owner}/{repo} not found — run `envsyncer setup`.")
    elif not data.get("private"):
        error(f"Vault repository {owner}/{repo} is PUBLIC — it must be private.")
    else:
        success(f"Vault reachable and private: {owner}/{repo}")


def _check_repo() -> None:
    try:
        repo, root = detect_repo()
    except EnvSyncerError as exc:
        warn(f"Not usable as a project here: {exc}")
        return
    success(f"Git repository detected: {repo.key} ({root})")
