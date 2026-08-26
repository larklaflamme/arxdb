"""ObjectStore — content-addressed put/get over a sharded filesystem.

Blobs are immutable and idempotent: `put(x)` always returns the same hash, and
re-putting an existing blob is a no-op. Files live under `objects/xx/…` where
`xx` is the first two hex chars of the hash (2-char shard). Writes are atomic
via temp-file + `os.replace`.

Public API (Phase 1):
    ObjectStore(root: Path)
        put(data: bytes) -> Hash
        put_batch(items: list[bytes]) -> list[Hash]
        get(h: Hash) -> bytes | None
        get_batch(hashes: list[Hash]) -> list[bytes | None]
        has(h: Hash) -> bool
        has_batch(hashes: list[Hash]) -> list[bool]
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from .hashing import Hash, hash_bytes


class ObjectStore:
    """Content-addressed blob store backed by a sharded filesystem."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, h: Hash) -> Path:
        """Filesystem path for a hash: `objects/{hex[:2]}/{hex[2:]}`."""
        hexstr = h.hex()
        return self.root / hexstr[:2] / hexstr[2:]

    def put(self, data: bytes) -> Hash:
        h = hash_bytes(data)
        dest = self._path(h)
        if dest.exists():
            return h
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.root / f".tmp_{uuid.uuid4().hex}"
        try:
            with open(tmp, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, dest)
        finally:
            if tmp.exists():
                tmp.unlink()
        return h

    def put_batch(self, items: list[bytes]) -> list[Hash]:
        return [self.put(item) for item in items]

    def get(self, h: Hash) -> bytes | None:
        dest = self._path(h)
        if not dest.exists():
            return None
        return dest.read_bytes()

    def get_batch(self, hashes: list[Hash]) -> list[bytes | None]:
        return [self.get(h) for h in hashes]

    def has(self, h: Hash) -> bool:
        return self._path(h).exists()

    def has_batch(self, hashes: list[Hash]) -> list[bool]:
        return [self.has(h) for h in hashes]
