"""`envsyncer doctor` — diagnose configuration and connectivity.

Read-only and non-interactive: it never triggers setup or prompts. Each check
prints a pass/fail line so a user (or a bug report) can see exactly what's wrong.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from envsyncer.core.config import Config
from envsyncer.core.discovery import discover_secrets
from envsyncer.core.github_client import GitHubClient
from envsyncer.core.local_repo import detect_repo
from envsyncer.core.profiles import DEFAULT_PROFILE
from envsyncer.core.vault import VaultManager
from envsyncer.ui.console import error, info, plain, success, warn
from envsyncer.utils import paths
from envsyncer.utils.errors import EnvSyncerError


def run(assume_yes: bool = False) -> None:  # noqa: ARG001 - uniform command signature
    info("Running EnvSyncer diagnostics…\n")
    config = Config.load()

    _check_config_file()
    _check_patterns(config)
    client = _check_token(config)
    if client is not None:
        _check_vault(config, client)
    _check_project(config, client)


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


def _check_patterns(config: Config) -> None:
    contradictions = sorted(set(config.include_patterns()) & set(config.exclude_patterns()))
    if contradictions:
        warn("These patterns are both included and excluded, so they never sync:")
        for pattern in contradictions:
            plain(f"    • {pattern}")
        plain("[dim]    Fix with `envsyncer exclude --remove <pattern>`.[/]")
    else:
        success(
            f"Scan patterns look consistent "
            f"({len(config.include_patterns())} custom include, "
            f"{len(config.exclude_patterns())} custom exclude)."
        )


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


def _check_project(config: Config, client: GitHubClient | None) -> None:
    try:
        repo, root = detect_repo()
    except EnvSyncerError as exc:
        warn(f"Not usable as a project here: {exc}")
        return
    success(f"Git repository detected: {repo.key} ({root})")

    found = discover_secrets(
        root,
        extra_includes=config.include_patterns(),
        extra_excludes=config.exclude_patterns(),
    )
    success(f"{len(found)} secret file(s) matched by the current patterns.")
    for secret in found:
        plain(f"    • {secret.relative_path}")

    if client is None:
        return
    profile = config.get_profile(repo.key) or DEFAULT_PROFILE
    try:
        tracked = VaultManager(client, config).read_profile_metadata(repo.key, profile)
    except EnvSyncerError as exc:
        error(f"Could not read profile '{profile}': {exc}")
        return

    matched = {secret.relative_path for secret in found}
    adopted = sorted(rel for rel in tracked if rel not in matched and (Path(root) / rel).exists())
    if adopted:
        info(f"Also synced because profile '{profile}' already tracks them:")
        for rel in adopted:
            plain(f"    • {rel}")
        plain("[dim]    `envsyncer add <name>` also matches them by pattern everywhere.[/]")

    missing = sorted(rel for rel in tracked if not (Path(root) / rel).exists())
    if missing:
        warn(f"In the vault ('{profile}') but not in this working tree:")
        for rel in missing:
            plain(f"    • {rel}")
        plain("[dim]    `envsyncer` downloads them; `envsyncer delete <path>` removes them.[/]")
    else:
        success(f"Every file in profile '{profile}' is present locally.")
