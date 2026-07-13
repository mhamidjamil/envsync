"""SHA-256 hashing — the sole basis for comparing files.

Content, never timestamps: two files are "the same" iff their bytes hash to
the same digest, regardless of mtime, on any platform.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK = 65536


def sha256_bytes(data: bytes) -> str:
    """Hex SHA-256 digest of an in-memory byte string."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    """Hex SHA-256 digest of a file, read in chunks to bound memory use."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()
