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

from pathlib import Path

from .hashing import Hash


class ObjectStore:
    """Content-addressed blob store backed by a sharded filesystem."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, data: bytes) -> Hash:
        raise NotImplementedError

    def put_batch(self, items: list[bytes]) -> list[Hash]:
        raise NotImplementedError

    def get(self, h: Hash) -> bytes | None:
        raise NotImplementedError

    def get_batch(self, hashes: list[Hash]) -> list[bytes | None]:
        raise NotImplementedError

    def has(self, h: Hash) -> bool:
        raise NotImplementedError

    def has_batch(self, hashes: list[Hash]) -> list[bool]:
        raise NotImplementedError
