"""Local baseline-hash cache.

After a successful sync we record, per project+profile, the SHA-256 each file
had at that moment. On the next run this "baseline" lets the sync engine tell
*who* changed:

* local differs, remote matches baseline  -> only local changed  -> upload
* remote differs, local matches baseline  -> only remote changed -> download
* both differ from baseline               -> genuine conflict

Without a baseline (first ever sync) divergence is treated conservatively as a
conflict — we never silently overwrite.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from envsyncer.utils import paths


def _cache_file(project_key: str, profile: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", f"{project_key}__{profile}")
    return paths.CACHE_DIR / f"{safe}.json"


def load_baseline(project_key: str, profile: str) -> dict[str, str]:
    """Return ``{relative_path: sha256}`` from the last sync, or ``{}``."""
    path = _cache_file(project_key, profile)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_baseline(project_key: str, profile: str, hashes: dict[str, str]) -> None:
    paths.ensure_dirs()
    path = _cache_file(project_key, profile)
    path.write_text(json.dumps(hashes, indent=2) + "\n", encoding="utf-8")
