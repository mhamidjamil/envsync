"""First-run setup: authentication and vault selection.

Runs automatically the first time any command needs GitHub access, and can be
re-run explicitly with ``envsyncer setup``. Idempotent: if configuration is
already complete it returns immediately unless ``force`` is set.
"""

from __future__ import annotations

import webbrowser

from envsyncer.core.config import DEFAULT_VAULT_REPO, Config
from envsyncer.core.github_client import GitHubClient
from envsyncer.ui import prompts
from envsyncer.ui.console import banner, info, plain, success, warn
from envsyncer.utils import paths
from envsyncer.utils.errors import AuthError, UserAbort
from envsyncer.utils.logging import get_logger

TOKEN_CREATE_URL = (
    "https://github.com/settings/tokens/new?scopes=repo&description=EnvSyncer"
)
FALLBACK_NEW_REPO_NAME = "self_envsyncer"

_log = get_logger()


def ensure_setup(assume_yes: bool = False) -> Config:
    """Return a fully configured :class:`Config`, running setup if needed."""
    paths.ensure_dirs()
    config = Config.load()
    if config.is_setup_complete():
        return config
    return run_setup(assume_yes=assume_yes, existing=config)


def run_setup(assume_yes: bool = False, existing: Config | None = None) -> Config:
    """Interactive setup flow. Returns the saved config."""
    config = existing or Config.load()

    banner(
        "Welcome to EnvSyncer",
        "Sync your project's secret files to a private GitHub vault.",
    )

    client = _authenticate(config, assume_yes=assume_yes)
    _setup_vault(config, client, assume_yes=assume_yes)

    config.save()
    success(f"Setup complete. Vault: [bold]{config.github_user}/{config.vault_repo}[/]")
    _log.info("setup complete user=%s vault=%s", config.github_user, config.vault_repo)
    return config


# -- authentication -------------------------------------------------------
def _authenticate(config: Config, *, assume_yes: bool) -> GitHubClient:
    if config.has_token():
        client = GitHubClient(config.github_token)
        try:
            user = client.get_authenticated_user()
        except AuthError:
            warn("Stored token is no longer valid — let's set a new one.")
        else:
            config.set_github(config.github_token, user)
            return client

    token = _obtain_token(assume_yes=assume_yes)
    client = GitHubClient(token)
    user = client.get_authenticated_user()  # validates; raises AuthError if bad
    config.set_github(token, user)
    config.save()
    success(f"Authenticated as [bold]{user}[/].")
    _log.info("authenticated user=%s", user)
    return client


def _obtain_token(*, assume_yes: bool) -> str:
    if assume_yes:
        raise UserAbort(
            "No GitHub token configured. Run `envsyncer setup` interactively first."
        )

    info("EnvSyncer needs a GitHub Personal Access Token (scope: [bold]repo[/]).")
    choice = prompts.select(
        "How would you like to provide it?",
        [
            "I already have a token — paste it",
            "Open GitHub in my browser to create one",
        ],
        default_index=1,
    )
    if choice == 1:
        plain(f"  Opening: [dim]{TOKEN_CREATE_URL}[/]")
        _open_browser(TOKEN_CREATE_URL)
        info("Create the token, then copy it and paste it below.")

    for _ in range(3):
        token = prompts.ask_secret("Paste your GitHub token")
        if token:
            return token
        warn("Empty token — try again.")
    raise UserAbort("No token provided.")


def _open_browser(url: str) -> None:
    try:
        webbrowser.open(url)
    except Exception:  # pragma: no cover - headless environments
        warn("Could not open a browser automatically; open the URL above manually.")


# -- vault selection ------------------------------------------------------
def _setup_vault(config: Config, client: GitHubClient, *, assume_yes: bool) -> None:
    owner = config.github_user
    name = config.vault_repo or DEFAULT_VAULT_REPO
    repo = client.get_repo(owner, name)

    if repo is not None and repo.get("private"):
        config.vault_repo = name
        success(f"Using existing private vault [bold]{owner}/{name}[/].")
        return

    if repo is not None and not repo.get("private"):
        warn(f'Repository "{name}" exists but is PUBLIC. A vault must be private.')
        _choose_vault(config, client, assume_yes=assume_yes)
        return

    warn(f'Repository "{name}" was not found.')
    _choose_vault(config, client, assume_yes=assume_yes)


def _choose_vault(config: Config, client: GitHubClient, *, assume_yes: bool) -> None:
    index = prompts.select(
        "Choose how to set up your vault",
        [
            f"Create a new private repository (default: {FALLBACK_NEW_REPO_NAME})",
            "Enter another repository name",
            "Exit",
        ],
        assume_yes=assume_yes,
        default_index=0,
    )

    if index == 2:
        raise UserAbort("Setup cancelled.")

    if index == 1:
        name = prompts.ask_text("Repository name").strip()
        if not name:
            raise UserAbort("No repository name provided.")
        existing = client.get_repo(config.github_user, name)
        if existing is not None:
            if not existing.get("private"):
                raise UserAbort(f'"{name}" exists and is public — choose a different name.')
            config.vault_repo = name
            success(f"Using existing private vault [bold]{config.github_user}/{name}[/].")
            return
    else:
        name = FALLBACK_NEW_REPO_NAME

    _create_vault(config, client, name)


def _create_vault(config: Config, client: GitHubClient, name: str) -> None:
    info(f"Creating private repository [bold]{name}[/] …")
    client.create_private_repo(name)
    config.vault_repo = name
    success(f"Created private vault [bold]{config.github_user}/{name}[/].")
    _log.info("created vault repo=%s", name)
