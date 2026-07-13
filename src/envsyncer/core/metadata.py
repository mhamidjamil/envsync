"""Read/write the vault's sidecar metadata files.

Two kinds of metadata live *in the vault* (never touching the real secrets):

* ``<owner>/<repo>/<profile>/.envsyncer.json`` — the per-profile record of which
  files exist and their hashes. The keys are **relative paths**, which is what
  lets another machine restore each file to its exact original location.
* ``manifest.json`` at the vault root — a fast index of every project and its
  profiles.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from envsyncer.models import RemoteFile

PROFILE_META_FILENAME = ".envsyncer.json"
MANIFEST_FILENAME = "manifest.json"
META_VERSION = 1


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# -- per-profile metadata (.envsyncer.json) -------------------------------
def build_profile_metadata(project_key: str, profile: str, files: dict[str, RemoteFile]) -> dict[str, Any]:
    return {
        "version": META_VERSION,
        "project": project_key,
        "profile": profile,
        "last_sync": _now_iso(),
        "files": {
            rel: {"sha256": rf.sha256, "size": rf.size}
            for rel, rf in sorted(files.items())
        },
    }


def parse_profile_metadata(data: dict[str, Any]) -> dict[str, RemoteFile]:
    """Turn a ``.envsyncer.json`` payload into ``{relative_path: RemoteFile}``."""
    result: dict[str, RemoteFile] = {}
    for rel, entry in data.get("files", {}).items():
        result[rel] = RemoteFile(
            relative_path=rel,
            sha256=entry["sha256"],
            size=entry.get("size", 0),
        )
    return result


def dumps(data: dict[str, Any]) -> bytes:
    return (json.dumps(data, indent=2) + "\n").encode("utf-8")


# -- root manifest (manifest.json) ----------------------------------------
def update_manifest(manifest: dict[str, Any] | None, project_key: str, profiles: list[str]) -> dict[str, Any]:
    """Return a manifest with ``project_key`` refreshed to ``profiles``."""
    manifest = manifest or {"version": META_VERSION, "projects": {}}
    manifest.setdefault("projects", {})[project_key] = {
        "profiles": sorted(profiles),
        "updated_at": _now_iso(),
    }
    return manifest
