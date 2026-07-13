"""Exception hierarchy for EnvSyncer.

All errors that represent an expected, user-facing failure inherit from
:class:`EnvSyncerError`. The CLI catches these at the top level and prints a
clean message instead of a traceback; anything else bubbles up as a real bug.
"""

from __future__ import annotations


class EnvSyncerError(Exception):
    """Base class for all expected, user-facing errors."""


class ConfigError(EnvSyncerError):
    """Local configuration is missing or invalid."""


class AuthError(EnvSyncerError):
    """Authentication with GitHub failed (bad/expired token, missing scopes)."""


class GitHubError(EnvSyncerError):
    """A GitHub REST API call failed.

    Carries the HTTP status code so callers can distinguish, e.g., 404 (not
    found) from 401 (unauthorized) without parsing the message.
    """

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class LocalRepoError(EnvSyncerError):
    """The current directory is not inside a usable git repository."""


class VaultError(EnvSyncerError):
    """A problem occurred while reading from or writing to the secret vault."""


class UserAbort(EnvSyncerError):
    """The user explicitly chose to exit / cancel an interactive flow."""
