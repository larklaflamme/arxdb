"""AppendLog — signed, append-only log over SQLite.

Every entry is signed by the agent that produced it, and each entry commits to
the previous entry's hash, forming a hash chain. A Merkle tree over the entry
hashes gives inclusion proofs for the whole log.

Backed by SQLite (WAL mode), sharing `index.db` with GraphIndex.

Public API (Phase 1):
    AppendLog(db_path: Path, priv_key: bytes, pub_key: bytes,
              conn: sqlite3.Connection | None = None)
        append(entry: bytes) -> LogEntry
        get(seq: int) -> LogEntry | None
        len() -> int
        root_hash() -> Hash
        get_inclusion_proof(seq: int) -> MerkleInclusionProof
        verify_entry(entry: LogEntry) -> bool

When `conn` is provided, the instance shares that connection and does NOT
commit (the owner controls the transaction). When `conn` is None, the instance
opens its own connection and commits after each write.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from .hashing import Hash, hash_bytes
from .keys import sign, verify
from .merkle import MerkleInclusionProof, inclusion_proof, root_hash
from .serialization import canonical_encode

# Genesis entry 0 commits to the all-zero sentinel (not a valid multihash, but
# exactly 34 bytes so it round-trips through the Hash length check).
GENESIS_PREV_HASH = b"\x00" * 34


@dataclass(frozen=True)
class LogEntry:
    """A single signed append-log entry.

    Carries everything needed to verify it: the signature is over the canonical
    encoding of (seq, timestamp_ns, signer_pubkey, entry_hash, prev_log_hash),
    and `entry_hash` is the content hash of `payload`.
    """

    seq: int
    timestamp_ns: int
    signer_pubkey: bytes
    entry_hash: Hash
    prev_log_hash: Hash
    signature: bytes
    payload: bytes


def _signature_message(
    seq: int,
    timestamp_ns: int,
    signer_pubkey: bytes,
    entry_hash: Hash,
    prev_log_hash: Hash,
) -> bytes:
    """The exact bytes signed for an entry: canonical CBOR of the 5-tuple."""
    return canonical_encode(
        [seq, timestamp_ns, signer_pubkey, entry_hash, prev_log_hash]
    )


class AppendLog:
    """Signed append-only log over a shared SQLite database."""

    def __init__(
        self,
        db_path: Path,
        priv_key: bytes,
        pub_key: bytes,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.priv_key = priv_key
        self.pub_key = pub_key
        self._owns_conn = conn is None
        if self._owns_conn:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        else:
            self._conn = conn
        self._init_schema()

    def _commit(self) -> None:
        """Commit only if this instance owns its connection."""
        if self._owns_conn:
            self._conn.commit()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS log (
                seq INTEGER PRIMARY KEY,
                timestamp_ns INTEGER NOT NULL,
                signer_pubkey BLOB NOT NULL,
                entry_hash BLOB NOT NULL,
                prev_log_hash BLOB NOT NULL,
                signature BLOB NOT NULL,
                payload BLOB NOT NULL
            )
            """
        )
        self._commit()

    def _prev_hash(self, seq: int) -> Hash:
        """The previous entry's hash, or the genesis sentinel for seq 0."""
        if seq == 0:
            return Hash(GENESIS_PREV_HASH)
        row = self._conn.execute(
            "SELECT entry_hash FROM log WHERE seq = ?", (seq - 1,)
        ).fetchone()
        return Hash(row[0])

    def append(self, entry: bytes) -> LogEntry:
        seq = self._conn.execute("SELECT COUNT(*) FROM log").fetchone()[0]
        timestamp_ns = time.time_ns()
        entry_hash = hash_bytes(entry)
        prev_log_hash = self._prev_hash(seq)
        message = _signature_message(
            seq, timestamp_ns, self.pub_key, entry_hash, prev_log_hash
        )
        signature = sign(self.priv_key, message)
        self._conn.execute(
            "INSERT INTO log "
            "(seq, timestamp_ns, signer_pubkey, entry_hash, prev_log_hash, "
            " signature, payload) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                seq,
                timestamp_ns,
                self.pub_key,
                bytes(entry_hash),
                bytes(prev_log_hash),
                signature,
                entry,
            ),
        )
        self._commit()
        return LogEntry(
            seq,
            timestamp_ns,
            self.pub_key,
            entry_hash,
            prev_log_hash,
            signature,
            entry,
        )

    def get(self, seq: int) -> LogEntry | None:
        row = self._conn.execute(
            "SELECT seq, timestamp_ns, signer_pubkey, entry_hash, prev_log_hash, "
            "signature, payload FROM log WHERE seq = ?",
            (seq,),
        ).fetchone()
        if row is None:
            return None
        return LogEntry(
            seq=row[0],
            timestamp_ns=row[1],
            signer_pubkey=row[2],
            entry_hash=Hash(row[3]),
            prev_log_hash=Hash(row[4]),
            signature=row[5],
            payload=row[6],
        )

    def __len__(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM log").fetchone()[0]

    def _entry_hashes(self) -> list[Hash]:
        rows = self._conn.execute(
            "SELECT entry_hash FROM log ORDER BY seq"
        ).fetchall()
        return [Hash(r[0]) for r in rows]

    def root_hash(self) -> Hash:
        return root_hash(self._entry_hashes())

    def get_inclusion_proof(self, seq: int) -> MerkleInclusionProof:
        hashes = self._entry_hashes()
        if seq < 0 or seq >= len(hashes):
            raise IndexError(f"seq {seq} out of range [0, {len(hashes)})")
        return inclusion_proof(hashes, seq)

    def verify_entry(self, entry: LogEntry) -> bool:
        """Verify an entry's signature and payload integrity.

        Returns True iff (a) `entry_hash` is the content hash of `payload`, and
        (b) the signature is valid over the entry's metadata.
        """
        if hash_bytes(entry.payload) != entry.entry_hash:
            return False
        message = _signature_message(
            entry.seq,
            entry.timestamp_ns,
            entry.signer_pubkey,
            entry.entry_hash,
            entry.prev_log_hash,
        )
        return verify(entry.signer_pubkey, message, entry.signature)
