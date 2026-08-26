"""Storage — the unified facade and the atomic `commit_edge_tx`.

`Storage` composes ObjectStore, GraphIndex, and AppendLog behind one interface.
The single most important method is `commit_edge_tx`, which commits a reasoning
edge *atomically* across all three sub-interfaces.

Atomicity is real (not rollback-on-exception) because GraphIndex and AppendLog
share one SQLite connection: the graph mutation and the log append happen inside
a single `BEGIN IMMEDIATE … COMMIT`. The ObjectStore write is idempotent, so an
orphaned blob is harmless rather than corruption.

Public API (Phase 1):
    Storage(root: Path, priv_key: bytes, pub_key: bytes)
        commit_edge_tx(premises, conclusion, edge_data, proof) -> (edge_hash, LogEntry)
        close() -> None
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .append_log import AppendLog, LogEntry
from .graph_index import GraphIndex
from .hashing import Hash, hash_bytes
from .object_store import ObjectStore


class Storage:
    """Unified storage facade: ObjectStore + GraphIndex + AppendLog."""

    def __init__(self, root: Path, priv_key: bytes, pub_key: bytes) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.objects = ObjectStore(self.root / "objects")
        # One shared connection so graph + log commit atomically. Autocommit
        # mode (isolation_level=None) gives us full manual control over the
        # explicit BEGIN IMMEDIATE … COMMIT in commit_edge_tx.
        self._conn = sqlite3.connect(
            str(self.root / "index.db"), isolation_level=None
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self.graph = GraphIndex(self.root / "index.db", conn=self._conn)
        self.log = AppendLog(
            self.root / "index.db", priv_key, pub_key, conn=self._conn
        )

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()

    def commit_edge_tx(
        self,
        premises: list[Hash],
        conclusion: Hash,
        edge_data: bytes,
        proof: bytes | None = None,
    ) -> tuple[Hash, LogEntry]:
        """Atomically commit a reasoning edge across all three sub-interfaces.

        Ordering (per the atomicity contract):
          1. ObjectStore writes (idempotent, no rollback needed).
          2. GraphIndex + AppendLog in one `BEGIN IMMEDIATE … COMMIT`.
        """
        edge_hash = hash_bytes(edge_data)
        # 1. ObjectStore: content-addressed and idempotent, so an orphaned
        #    blob is harmless rather than corruption.
        self.objects.put(edge_data)
        if proof is not None:
            self.objects.put(proof)
        # 2. Graph + log in a single transaction.
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self.graph.register_edge(edge_hash, premises, conclusion)
            log_entry = self.log.append(edge_data)
            self._conn.execute("COMMIT")
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        return edge_hash, log_entry
