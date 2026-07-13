"""Local configuration stored at ``~/.envsyncer/config.json``.

The file is plain JSON (portable — copy it between your *own* machines and the
tool works immediately). Because JSON has no comment syntax, human guidance is
carried in ``_readme`` / ``_docs`` string fields at the top of the file.

Security: the file holds a GitHub Personal Access Token, so it is written with
``0600`` permissions (owner read/write only). Never share it with other people —
a ``repo``-scoped PAT grants full access to all your private repositories.
"""

from __future__ import annotations

import json
import os
import stat
from typing import Any

from envsyncer.utils import paths
from envsyncer.utils.errors import ConfigError

CONFIG_VERSION = 1
DEFAULT_VAULT_REPO = "my-env"

_README = (
    "EnvSyncer configuration. Put your GitHub Personal Access Token in "
    "github.token below (or run `envsyncer setup`)."
)
_DOCS = "Create a token (scope: repo) at https://github.com/settings/tokens/new?scopes=repo&description=EnvSyncer"


def _blank_config() -> dict[str, Any]:
    """A fresh config skeleton with an empty token and a comment header."""
    return {
        "_readme": _README,
        "_docs": _DOCS,
        "version": CONFIG_VERSION,
        "github": {"token": "", "user": ""},
        "vault_repo": DEFAULT_VAULT_REPO,
        "projects": {},   # "owner/repo" -> {"profile": "..."}
        "settings": {},
    }


class Config:
    """In-memory view of the config file with typed accessors."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    # -- construction -----------------------------------------------------
    @classmethod
    def blank(cls) -> "Config":
        return cls(_blank_config())

    @classmethod
    def load(cls) -> "Config":
        """Load config from disk, or return a blank one if none exists yet."""
        if not paths.CONFIG_FILE.exists():
            return cls.blank()
        try:
            data = json.loads(paths.CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ConfigError(f"Config file is corrupt: {paths.CONFIG_FILE} ({exc})") from exc
        # Merge onto a blank skeleton so older/partial files gain new keys.
        merged = _blank_config()
        merged.update({k: v for k, v in data.items() if k not in ("github",)})
        merged["github"].update(data.get("github", {}))
        return cls(merged)

    def save(self) -> None:
        """Persist to disk with ``0600`` permissions."""
        paths.ensure_dirs()
        paths.CONFIG_FILE.write_text(
            json.dumps(self._data, indent=2) + "\n", encoding="utf-8"
        )
        try:
            os.chmod(paths.CONFIG_FILE, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            # Best-effort on platforms where chmod is a no-op (e.g. some Windows setups).
            pass

    # -- github token -----------------------------------------------------
    @property
    def github_token(self) -> str:
        return self._data["github"].get("token", "")

    @property
    def github_user(self) -> str:
        return self._data["github"].get("user", "")

    def set_github(self, token: str, user: str) -> None:
        self._data["github"]["token"] = token
        self._data["github"]["user"] = user

    def has_token(self) -> bool:
        return bool(self.github_token.strip())

    # -- vault ------------------------------------------------------------
    @property
    def vault_repo(self) -> str:
        return self._data.get("vault_repo", DEFAULT_VAULT_REPO)

    @vault_repo.setter
    def vault_repo(self, name: str) -> None:
        self._data["vault_repo"] = name

    def is_setup_complete(self) -> bool:
        return self.has_token() and bool(self.github_user) and bool(self.vault_repo)

    # -- per-project profile ---------------------------------------------
    def get_profile(self, repo_key: str) -> str | None:
        return self._data["projects"].get(repo_key, {}).get("profile")

    def set_profile(self, repo_key: str, profile: str) -> None:
        self._data["projects"].setdefault(repo_key, {})["profile"] = profile
