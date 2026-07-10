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

    def commit_files(
        self,
        owner: str,
        repo: str,
        branch: str,
        files: dict[str, bytes],
        message: str,
    ) -> None:
        """Write many files as a SINGLE commit via the Git Data API.

        Steps: resolve the branch tip -> its base tree -> upload each file as a
        blob -> build one new tree on top of the base -> create one commit ->
        fast-forward the branch ref. The result is exactly one commit no matter
        how many files changed.
        """
        if not files:
            return

        base_commit_sha = self._get_ref_sha(owner, repo, branch)
        base_tree_sha = self._get_commit_tree(owner, repo, base_commit_sha)

        tree = [
            {
                "path": path,
                "mode": "100644",
                "type": "blob",
                "sha": self._create_blob(owner, repo, content),
            }
            for path, content in files.items()
        ]

        new_tree_sha = self._post_json(
            f"/repos/{owner}/{repo}/git/trees",
            {"base_tree": base_tree_sha, "tree": tree},
            "create tree",
        )["sha"]
        new_commit_sha = self._post_json(
            f"/repos/{owner}/{repo}/git/commits",
            {"message": message, "tree": new_tree_sha, "parents": [base_commit_sha]},
            "create commit",
        )["sha"]

        response = self._request(
            "PATCH",
            f"/repos/{owner}/{repo}/git/refs/heads/{branch}",
            json={"sha": new_commit_sha, "force": False},
        )
        if not response.ok:
            raise GitHubError(
                f"Failed to update branch '{branch}': {self._json_error(response)}",
                response.status_code,
            )

    # -- git data helpers -------------------------------------------------
    def _get_ref_sha(self, owner: str, repo: str, branch: str) -> str:
        response = self._request("GET", f"/repos/{owner}/{repo}/git/ref/heads/{branch}")
        if not response.ok:
            raise GitHubError(
                f"Could not resolve branch '{branch}': {self._json_error(response)}",
                response.status_code,
            )
        return response.json()["object"]["sha"]

    def _get_commit_tree(self, owner: str, repo: str, commit_sha: str) -> str:
        response = self._request("GET", f"/repos/{owner}/{repo}/git/commits/{commit_sha}")
        if not response.ok:
            raise GitHubError(self._json_error(response), response.status_code)
        return response.json()["tree"]["sha"]

    def _create_blob(self, owner: str, repo: str, content: bytes) -> str:
        return self._post_json(
            f"/repos/{owner}/{repo}/git/blobs",
            {"content": base64.b64encode(content).decode("ascii"), "encoding": "base64"},
            "create blob",
        )["sha"]

    def _post_json(self, path: str, body: dict[str, Any], what: str) -> dict[str, Any]:
        response = self._request("POST", path, json=body)
        if not response.ok:
            raise GitHubError(f"Failed to {what}: {self._json_error(response)}", response.status_code)
        return response.json()
