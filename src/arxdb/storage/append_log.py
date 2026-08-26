"""AppendLog — signed, append-only log over SQLite.

Every entry is signed by the agent that produced it, and each entry commits to
the previous entry's hash, forming a hash chain. A Merkle tree over the entry
hashes gives inclusion proofs for the whole log.

Backed by SQLite (WAL mode), sharing `index.db` with GraphIndex.

Public API (Phase 1):
    AppendLog(db_path: Path, priv_key: bytes, pub_key: bytes)
        append(entry: bytes) -> LogEntry
        get(seq: int) -> LogEntry | None
        len() -> int
        root_hash() -> Hash
        get_inclusion_proof(seq: int) -> MerkleInclusionProof
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .hashing import Hash
from .merkle import MerkleInclusionProof


@dataclass(frozen=True)
class LogEntry:
    """A single signed append-log entry."""

    seq: int
    entry_hash: Hash
    prev_log_hash: Hash
    signature: bytes
    payload: bytes


class AppendLog:
    """Signed append-only log over a shared SQLite database."""

    def __init__(self, db_path: Path, priv_key: bytes, pub_key: bytes) -> None:
        self.db_path = Path(db_path)
        self.priv_key = priv_key
        self.pub_key = pub_key
        self._init_schema()

    def _init_schema(self) -> None:
        raise NotImplementedError

    def append(self, entry: bytes) -> LogEntry:
        raise NotImplementedError

    def get(self, seq: int) -> LogEntry | None:
        raise NotImplementedError

    def __len__(self) -> int:
        raise NotImplementedError

    def root_hash(self) -> Hash:
        raise NotImplementedError

    def get_inclusion_proof(self, seq: int) -> MerkleInclusionProof:
        raise NotImplementedError
