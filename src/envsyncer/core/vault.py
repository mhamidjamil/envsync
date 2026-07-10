"""High-level access to the secret vault repository.

Owns the single source of truth for the vault path layout:

    <project_owner>/<project_repo>/<profile>/<relative_path>

The vault repository itself always belongs to the authenticated user
(``config.github_user``); ``<project_owner>/<project_repo>`` is only a logical
folder key. Callers never build vault paths by hand — they go through here.
"""

from __future__ import annotations

import json
from typing import Any

from envsyncer.core import metadata
from envsyncer.core.config import Config
from envsyncer.core.github_client import GitHubClient
from envsyncer.models import RemoteFile
from envsyncer.utils.errors import VaultError


class VaultManager:
    def __init__(self, client: GitHubClient, config: Config) -> None:
        self._client = client
        self._config = config
        self._owner = config.github_user
        self._repo = config.vault_repo
        self._branch: str | None = None
        # Pending writes (vault_path -> content) flushed together by commit().
        self._staged: dict[str, bytes] = {}

    # -- path mapping -----------------------------------------------------
    def profile_root(self, project_key: str, profile: str) -> str:
        return f"{project_key}/{profile}"

    def vault_path(self, project_key: str, profile: str, relative_path: str) -> str:
        return f"{project_key}/{profile}/{relative_path}"

    # -- lazy repo info ---------------------------------------------------
    @property
    def branch(self) -> str:
        """Default branch of the vault repo (cached after first lookup)."""
        if self._branch is None:
            repo = self._client.get_repo(self._owner, self._repo)
            if repo is None:
                raise VaultError(
                    f"Vault repository '{self._owner}/{self._repo}' was not found. "
                    "Run `envsyncer setup` to (re)create it."
                )
            self._branch = repo.get("default_branch", "main")
        return self._branch

    # -- profiles ---------------------------------------------------------
    def list_profiles(self, project_key: str) -> list[str]:
        """Return the profile names recorded for a project (dirs in the vault)."""
        entries = self._client.list_dir(self._owner, self._repo, project_key, ref=self.branch)
        return sorted(e["name"] for e in entries if e.get("type") == "dir")

    def read_profile_metadata(self, project_key: str, profile: str) -> dict[str, RemoteFile]:
        """Load a profile's ``.envsyncer.json`` into ``{relative_path: RemoteFile}``."""
        path = self.vault_path(project_key, profile, metadata.PROFILE_META_FILENAME)
        result = self._client.get_file(self._owner, self._repo, path, ref=self.branch)
        if result is None:
            return {}
        try:
            data = json.loads(result[0].decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise VaultError(f"Corrupt metadata for profile '{profile}': {exc}") from exc
        return metadata.parse_profile_metadata(data)

    # -- reads ------------------------------------------------------------
    def download(self, project_key: str, profile: str, relative_path: str) -> bytes:
        path = self.vault_path(project_key, profile, relative_path)
        result = self._client.get_file(self._owner, self._repo, path, ref=self.branch)
        if result is None:
            raise VaultError(f"Expected file missing from vault: {path}")
        return result[0]

    # -- staging (all writes go here, then a single commit) ---------------
    def stage_file(self, project_key: str, profile: str, relative_path: str, content: bytes) -> None:
        self._staged[self.vault_path(project_key, profile, relative_path)] = content

    def stage_profile_metadata(self, project_key: str, profile: str, files: dict[str, RemoteFile]) -> None:
        data = metadata.build_profile_metadata(project_key, profile, files)
        path = self.vault_path(project_key, profile, metadata.PROFILE_META_FILENAME)
        self._staged[path] = metadata.dumps(data)

    def stage_manifest(self, project_key: str, profile: str) -> None:
        """Stage a refreshed root ``manifest.json`` for this project.

        Profiles = those already committed plus the one being written now (which
        isn't committed yet, so it wouldn't show up in a directory listing).
        """
        existing = self._client.get_file(
            self._owner, self._repo, metadata.MANIFEST_FILENAME, ref=self.branch
        )
        current: dict[str, Any] | None = None
        if existing is not None:
            try:
                current = json.loads(existing[0].decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                current = None
        profiles = sorted(set(self.list_profiles(project_key)) | {profile})
        updated = metadata.update_manifest(current, project_key, profiles)
        self._staged[metadata.MANIFEST_FILENAME] = metadata.dumps(updated)

    def has_staged(self) -> bool:
        return bool(self._staged)

    def commit(self, message: str) -> None:
        """Flush all staged writes as one commit; no-op if nothing is staged."""
        if not self._staged:
            return
        self._client.commit_files(self._owner, self._repo, self.branch, self._staged, message)
        self._staged.clear()
