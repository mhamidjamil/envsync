"""Thin, typed wrapper over the GitHub REST API.

This is the *only* module that speaks HTTP to GitHub — everything else talks in
domain terms. That keeps the API surface swappable (e.g. a future git-clone
backend) and makes the rest of the code easy to test by mocking this class.

Vault writes go through the Contents API: a ``PUT .../contents/{path}`` call is
itself a commit + push on GitHub, so syncing is auto-committed with no local
git state to manage.
"""

from __future__ import annotations

import base64
from typing import Any

import requests

from envsyncer.utils.errors import AuthError, GitHubError

API_ROOT = "https://api.github.com"
_TIMEOUT = 30


class GitHubClient:
    def __init__(self, token: str) -> None:
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "envsyncer",
            }
        )

    # -- low-level --------------------------------------------------------
    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        url = path if path.startswith("http") else f"{API_ROOT}{path}"
        try:
            response = self._session.request(method, url, timeout=_TIMEOUT, **kwargs)
        except requests.RequestException as exc:
            raise GitHubError(f"Network error talking to GitHub: {exc}") from exc

        if response.status_code == 401:
            raise AuthError("GitHub rejected the token (401). It may be invalid or expired.")
        if response.status_code == 403 and "rate limit" in response.text.lower():
            raise GitHubError("GitHub API rate limit exceeded. Try again shortly.", 403)
        return response

    @staticmethod
    def _json_error(response: requests.Response) -> str:
        try:
            return response.json().get("message", response.text)
        except ValueError:
            return response.text

    # -- identity ---------------------------------------------------------
    def get_authenticated_user(self) -> str:
        """Return the login of the token owner; validates the token."""
        response = self._request("GET", "/user")
        if not response.ok:
            raise AuthError(f"Could not authenticate: {self._json_error(response)}")
        return response.json()["login"]

    # -- repositories -----------------------------------------------------
    def get_repo(self, owner: str, repo: str) -> dict[str, Any] | None:
        """Return the repo object, or ``None`` if it does not exist (404)."""
        response = self._request("GET", f"/repos/{owner}/{repo}")
        if response.status_code == 404:
            return None
        if not response.ok:
            raise GitHubError(self._json_error(response), response.status_code)
        return response.json()

    def create_private_repo(self, name: str) -> dict[str, Any]:
        """Create a private repo (auto-initialised so it has a default branch)."""
        response = self._request(
            "POST",
            "/user/repos",
            json={
                "name": name,
                "private": True,
                "auto_init": True,
                "description": "EnvSyncer secret vault — do not make public.",
            },
        )
        if not response.ok:
            raise GitHubError(
                f"Failed to create repository '{name}': {self._json_error(response)}",
                response.status_code,
            )
        return response.json()

    # -- contents ---------------------------------------------------------
    def get_file(self, owner: str, repo: str, path: str, ref: str | None = None) -> tuple[bytes, str] | None:
        """Return ``(content_bytes, blob_sha)`` for a file, or ``None`` if absent."""
        params = {"ref": ref} if ref else None
        response = self._request("GET", f"/repos/{owner}/{repo}/contents/{path}", params=params)
        if response.status_code == 404:
            return None
        if not response.ok:
            raise GitHubError(self._json_error(response), response.status_code)
        payload = response.json()
        content = base64.b64decode(payload["content"])
        return content, payload["sha"]

    def list_dir(self, owner: str, repo: str, path: str, ref: str | None = None) -> list[dict[str, Any]]:
        """Return directory entries, or an empty list if the path is absent."""
        params = {"ref": ref} if ref else None
        response = self._request("GET", f"/repos/{owner}/{repo}/contents/{path}", params=params)
        if response.status_code == 404:
            return []
        if not response.ok:
            raise GitHubError(self._json_error(response), response.status_code)
        payload = response.json()
        return payload if isinstance(payload, list) else []

    def put_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: bytes,
        message: str,
        branch: str | None = None,
    ) -> None:
        """Create or update a file (an auto-commit). Fetches the blob sha if updating."""
        existing = self.get_file(owner, repo, path, ref=branch)
        body: dict[str, Any] = {
            "message": message,
            "content": base64.b64encode(content).decode("ascii"),
        }
        if branch:
            body["branch"] = branch
        if existing is not None:
            body["sha"] = existing[1]

        response = self._request("PUT", f"/repos/{owner}/{repo}/contents/{path}", json=body)
        if not response.ok:
            raise GitHubError(
                f"Failed to write '{path}': {self._json_error(response)}",
                response.status_code,
            )
