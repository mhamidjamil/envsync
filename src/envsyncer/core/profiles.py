"""Resolve and switch the active profile for a project.

Resolution order for the default sync:

1. A profile remembered for this project in the config -> use it silently.
2. No remembered profile:
   * no profiles in the vault yet          -> default ``main`` (new project)
   * exactly one profile in the vault       -> use it
   * several profiles                        -> show the numbered menu
     (option to "Create New", suggesting ``dev``).

The chosen profile is saved back to the config so future runs are silent.
"""

from __future__ import annotations

from envsyncer.core.config import Config
from envsyncer.core.vault import VaultManager
from envsyncer.ui import prompts
from envsyncer.ui.console import info

DEFAULT_PROFILE = "main"
SUGGESTED_NEW_PROFILE = "dev"


def resolve_active_profile(
    config: Config,
    vault: VaultManager,
    project_key: str,
    *,
    assume_yes: bool = False,
) -> str:
    """Return the profile to sync, prompting only when genuinely ambiguous."""
    remembered = config.get_profile(project_key)
    if remembered:
        return remembered

    remote_profiles = vault.list_profiles(project_key)

    if not remote_profiles:
        chosen = DEFAULT_PROFILE
    elif len(remote_profiles) == 1:
        chosen = remote_profiles[0]
    else:
        chosen = _choose_from_menu(remote_profiles, assume_yes=assume_yes)

    config.set_profile(project_key, chosen)
    config.save()
    info(f"Active profile: [bold]{chosen}[/]")
    return chosen


def _choose_from_menu(remote_profiles: list[str], *, assume_yes: bool) -> str:
    options = [*remote_profiles, "Create New"]
    index = prompts.select(
        "Profiles found", options, assume_yes=assume_yes, default_index=0
    )
    if index < len(remote_profiles):
        return remote_profiles[index]
    name = prompts.ask_text("New profile name", default=SUGGESTED_NEW_PROFILE).strip()
    return name or SUGGESTED_NEW_PROFILE


def switch_profile(config: Config, project_key: str, name: str) -> None:
    """Persist ``name`` as the active profile for a project."""
    config.set_profile(project_key, name)
    config.save()
